/* SPDX-License-Identifier: ISC */
/*
 * Exynos990 HSI1 S2MPU-aware DMA wrappers for the z3s BCM4375 port.
 */

#ifndef BRCMFMAC_S2MPU_H
#define BRCMFMAC_S2MPU_H

#include <linux/dma-mapping.h>

void *brcmf_dma_alloc_coherent(struct device *dev, size_t size,
			       dma_addr_t *dma_handle, gfp_t gfp);
void brcmf_dma_free_coherent(struct device *dev, size_t size,
			     void *cpu_addr, dma_addr_t dma_handle);
dma_addr_t brcmf_dma_map_single(struct device *dev, void *cpu_addr,
				size_t size,
				enum dma_data_direction direction);
void brcmf_dma_unmap_single(struct device *dev, dma_addr_t dma_addr,
			    size_t size,
			    enum dma_data_direction direction);

/*
 * bus.h includes this after the normal DMA API headers.  Restrict the
 * substitutions to brcmfmac translation units.  The implementation defines
 * BRCMFMAC_S2MPU_IMPLEMENTATION and calls the attrs forms of the underlying
 * DMA API directly.
 */
#ifndef BRCMFMAC_S2MPU_IMPLEMENTATION
#undef dma_alloc_coherent
#undef dma_free_coherent
#undef dma_map_single
#undef dma_unmap_single
#define dma_alloc_coherent	brcmf_dma_alloc_coherent
#define dma_free_coherent	brcmf_dma_free_coherent
#define dma_map_single		brcmf_dma_map_single
#define dma_unmap_single	brcmf_dma_unmap_single
#endif

#endif /* BRCMFMAC_S2MPU_H */
