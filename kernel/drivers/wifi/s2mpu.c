// SPDX-License-Identifier: ISC
/*
 * Samsung Exynos990 protects PCIe DMA with an EL2-managed stage-2 memory
 * protection unit (S2MPU).  The stock z3s kernel grants and revokes HSI1
 * access in its DMA map operations.  Mainline DMA operations do not know
 * about that vendor ABI, so BCM4375 firmware boots but traps on its first
 * host-memory transfer.
 *
 * Keep this compatibility layer local to Samsung's BCM4375 PCI ID.  It
 * wraps every coherent and streaming DMA mapping used by brcmfmac and
 * mirrors the stock 64 KiB reference-counted grant scheme.
 */

#include <linux/arm-smccc.h>
#include <linux/dma-mapping.h>
#include <linux/kernel.h>
#include <linux/pci.h>
#include <linux/spinlock.h>

#define BRCMFMAC_S2MPU_IMPLEMENTATION
#include "s2mpu.h"

#define BCM4375_VENDOR_ID		0x14e4
#define BCM4375_PCIE_DEVICE_ID		0x4475
#define BCM43752_PCIE_DEVICE_ID		0x449d

#define EXYNOS_HVC_SET_S2MPU_FOR_WIFI	0xc6000101UL
#define EXYNOS_S2MPU_WIFI_VID		1UL
#define EXYNOS_S2MPU_HSI1_INDEX		24UL
#define EXYNOS_S2MPU_ARG1		((EXYNOS_S2MPU_WIFI_VID << 16) | \
					 EXYNOS_S2MPU_HSI1_INDEX)

#define EXYNOS_S2MPU_NO_ACCESS		0UL
#define EXYNOS_S2MPU_READ_WRITE		3UL
#define EXYNOS_S2MPU_GRANULE		SZ_64K
#define EXYNOS_S2MPU_LOW_RAM_BASE	0x80000000ULL
#define EXYNOS_S2MPU_LOW_RAM_END	0x100000000ULL
#define EXYNOS_S2MPU_LOW_RAM_PAGES	((EXYNOS_S2MPU_LOW_RAM_END - \
					  EXYNOS_S2MPU_LOW_RAM_BASE) / \
					 EXYNOS_S2MPU_GRANULE)

static DEFINE_SPINLOCK(brcmf_s2mpu_lock);
static u32 brcmf_s2mpu_refs[EXYNOS_S2MPU_LOW_RAM_PAGES];

static bool brcmf_s2mpu_required(struct device *dev)
{
	struct pci_dev *pdev;

	if (!dev_is_pci(dev))
		return false;

	pdev = to_pci_dev(dev);
	return pdev->vendor == BCM4375_VENDOR_ID &&
	       (pdev->device == BCM4375_PCIE_DEVICE_ID || pdev->device == BCM43752_PCIE_DEVICE_ID);
}

static unsigned long brcmf_s2mpu_hvc(dma_addr_t base,
				     unsigned long permission)
{
	struct arm_smccc_res res = {};

	/* Samsung's exynos_hvc() executes a full-system barrier first. */
	mb();
	arm_smccc_hvc(EXYNOS_HVC_SET_S2MPU_FOR_WIFI,
		      EXYNOS_S2MPU_ARG1, base, EXYNOS_S2MPU_GRANULE,
		      permission, 0, 0, 0, &res);
	mb();

	return res.a0;
}

static int brcmf_s2mpu_bounds(dma_addr_t dma_addr, size_t size,
			      dma_addr_t *first, dma_addr_t *last)
{
	u64 end;

	if (!size)
		return -EINVAL;
	if (check_add_overflow((u64)dma_addr, (u64)size, &end))
		return -EOVERFLOW;

	*first = round_down(dma_addr, (dma_addr_t)EXYNOS_S2MPU_GRANULE);
	*last = round_up(end, (u64)EXYNOS_S2MPU_GRANULE);

	if (*first < EXYNOS_S2MPU_LOW_RAM_BASE ||
	    *last > EXYNOS_S2MPU_LOW_RAM_END)
		return -ERANGE;

	return 0;
}

static int brcmf_s2mpu_grant(struct device *dev, dma_addr_t dma_addr,
			     size_t size)
{
	dma_addr_t first;
	dma_addr_t last;
	dma_addr_t addr;
	unsigned long flags;
	unsigned long hvc_ret;
	u32 index;
	int ret;

	ret = brcmf_s2mpu_bounds(dma_addr, size, &first, &last);
	if (ret) {
		dev_err(dev, "S2MPU cannot cover DMA %pad+%zu: %d\n",
			&dma_addr, size, ret);
		return ret;
	}

	spin_lock_irqsave(&brcmf_s2mpu_lock, flags);
	for (addr = first; addr < last; addr += EXYNOS_S2MPU_GRANULE) {
		index = (addr - EXYNOS_S2MPU_LOW_RAM_BASE) /
			EXYNOS_S2MPU_GRANULE;
		if (brcmf_s2mpu_refs[index] == U32_MAX) {
			ret = -EOVERFLOW;
			goto rollback;
		}
		if (!brcmf_s2mpu_refs[index]) {
			hvc_ret = brcmf_s2mpu_hvc(addr,
						 EXYNOS_S2MPU_READ_WRITE);
			if (hvc_ret) {
				dev_err(dev,
					"S2MPU grant failed for %pad: 0x%lx\n",
					&addr, hvc_ret);
				ret = -EIO;
				goto rollback;
			}
		}
		brcmf_s2mpu_refs[index]++;
	}
	spin_unlock_irqrestore(&brcmf_s2mpu_lock, flags);

	pr_info_once("brcmfmac: Exynos990 HSI1 S2MPU DMA grants enabled\n");
	return 0;

rollback:
	while (addr > first) {
		addr -= EXYNOS_S2MPU_GRANULE;
		index = (addr - EXYNOS_S2MPU_LOW_RAM_BASE) /
			EXYNOS_S2MPU_GRANULE;
		brcmf_s2mpu_refs[index]--;
		if (!brcmf_s2mpu_refs[index])
			brcmf_s2mpu_hvc(addr, EXYNOS_S2MPU_NO_ACCESS);
	}
	spin_unlock_irqrestore(&brcmf_s2mpu_lock, flags);
	return ret;
}

static void brcmf_s2mpu_revoke(struct device *dev, dma_addr_t dma_addr,
			       size_t size)
{
	dma_addr_t first;
	dma_addr_t last;
	dma_addr_t addr;
	unsigned long flags;
	unsigned long hvc_ret;
	u32 index;
	int ret;

	ret = brcmf_s2mpu_bounds(dma_addr, size, &first, &last);
	if (ret) {
		dev_err(dev, "S2MPU cannot revoke DMA %pad+%zu: %d\n",
			&dma_addr, size, ret);
		return;
	}

	spin_lock_irqsave(&brcmf_s2mpu_lock, flags);
	for (addr = first; addr < last; addr += EXYNOS_S2MPU_GRANULE) {
		index = (addr - EXYNOS_S2MPU_LOW_RAM_BASE) /
			EXYNOS_S2MPU_GRANULE;
		if (!brcmf_s2mpu_refs[index]) {
			dev_warn(dev, "unbalanced S2MPU revoke for %pad\n",
				 &addr);
			continue;
		}

		brcmf_s2mpu_refs[index]--;
		if (!brcmf_s2mpu_refs[index]) {
			hvc_ret = brcmf_s2mpu_hvc(addr,
						  EXYNOS_S2MPU_NO_ACCESS);
			if (hvc_ret) {
				dev_err(dev,
					"S2MPU revoke failed for %pad: 0x%lx\n",
					&addr, hvc_ret);
				brcmf_s2mpu_refs[index]++;
			}
		}
	}
	spin_unlock_irqrestore(&brcmf_s2mpu_lock, flags);
}

void *brcmf_dma_alloc_coherent(struct device *dev, size_t size,
			       dma_addr_t *dma_handle, gfp_t gfp)
{
	void *cpu_addr;

	cpu_addr = dma_alloc_attrs(dev, size, dma_handle, gfp, 0);
	if (!cpu_addr || !brcmf_s2mpu_required(dev))
		return cpu_addr;

	if (brcmf_s2mpu_grant(dev, *dma_handle, size)) {
		dma_free_attrs(dev, size, cpu_addr, *dma_handle, 0);
		return NULL;
	}

	return cpu_addr;
}

void brcmf_dma_free_coherent(struct device *dev, size_t size,
			     void *cpu_addr, dma_addr_t dma_handle)
{
	if (brcmf_s2mpu_required(dev))
		brcmf_s2mpu_revoke(dev, dma_handle, size);
	dma_free_attrs(dev, size, cpu_addr, dma_handle, 0);
}

dma_addr_t brcmf_dma_map_single(struct device *dev, void *cpu_addr,
				size_t size,
				enum dma_data_direction direction)
{
	dma_addr_t dma_addr;

	dma_addr = dma_map_single_attrs(dev, cpu_addr, size, direction, 0);
	if (dma_mapping_error(dev, dma_addr) || !brcmf_s2mpu_required(dev))
		return dma_addr;

	if (brcmf_s2mpu_grant(dev, dma_addr, size)) {
		dma_unmap_single_attrs(dev, dma_addr, size, direction, 0);
		return DMA_MAPPING_ERROR;
	}

	return dma_addr;
}

void brcmf_dma_unmap_single(struct device *dev, dma_addr_t dma_addr,
			    size_t size,
			    enum dma_data_direction direction)
{
	if (brcmf_s2mpu_required(dev))
		brcmf_s2mpu_revoke(dev, dma_addr, size);
	dma_unmap_single_attrs(dev, dma_addr, size, direction, 0);
}
