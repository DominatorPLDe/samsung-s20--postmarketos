// SPDX-License-Identifier: GPL-2.0-only
/*
 * Copyright 2020 Samsung Electronics Co., Ltd.
 * Copyright 2020 Google LLC.
 * Copyright 2024 Linaro Ltd.
 */

#include <linux/bitops.h>
#include <linux/bits.h>
#include <linux/clk.h>
#include <linux/io.h>
#include <linux/mailbox_controller.h>
#include <linux/mailbox/exynos-message.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/slab.h>

#define EXYNOS_MBOX_INTMR0		0x28	/* Interrupt Mask Register 0 */
#define EXYNOS_MBOX_INTGR1		0x40	/* Interrupt Generation Register 1 */

#define EXYNOS_MBOX_INTMR0_MASK		GENMASK(15, 0)
#define EXYNOS_MBOX_INTGR1_MASK		GENMASK(15, 0)

#define EXYNOS_MBOX_CHAN_COUNT		HWEIGHT32(EXYNOS_MBOX_INTGR1_MASK)

/*
 * The AP->APM doorbell register and its encoding differ per SoC.
 * gs101:     write BIT(chan_id)       to INTGR1 (0x40); mask INTMR0 at 0x28.
 * exynos990: write BIT(chan_id) << 16 to INTGR0 (0x08); mask INTMR0 at 0x10.
 */
struct exynos_mbox_data {
	u32 intmr0;
	u32 intmr1;
	u32 doorbell_reg;
	u32 doorbell_shift;
};

static const struct exynos_mbox_data gs101_mbox_data = {
	.intmr0		= 0x28,
	.doorbell_reg	= 0x40,
	.doorbell_shift	= 0,
};

static const struct exynos_mbox_data exynos990_mbox_data = {
	.intmr0		= 0x10,
	.intmr1		= 0x24,
	.doorbell_reg	= 0x08,
	.doorbell_shift	= 16,
};

/**
 * struct exynos_mbox - driver's private data.
 * @regs:	mailbox registers base address.
 * @mbox:	pointer to the mailbox controller.
 */
struct exynos_mbox {
	void __iomem *regs;
	struct mbox_controller *mbox;
	const struct exynos_mbox_data *data;
};

static int exynos_mbox_send_data(struct mbox_chan *chan, void *data)
{
	struct device *dev = chan->mbox->dev;
	struct exynos_mbox *exynos_mbox = dev_get_drvdata(dev);
	struct exynos_mbox_msg *msg = data;

	if (msg->chan_id >= exynos_mbox->mbox->num_chans) {
		dev_err(dev, "Invalid channel ID %d\n", msg->chan_id);
		return -EINVAL;
	}

	if (msg->chan_type != EXYNOS_MBOX_CHAN_TYPE_DOORBELL) {
		dev_err(dev, "Unsupported channel type [%d]\n", msg->chan_type);
		return -EINVAL;
	}

	writel(BIT(msg->chan_id) << exynos_mbox->data->doorbell_shift,
	       exynos_mbox->regs + exynos_mbox->data->doorbell_reg);

	return 0;
}

static const struct mbox_chan_ops exynos_mbox_chan_ops = {
	.send_data = exynos_mbox_send_data,
};

static struct mbox_chan *exynos_mbox_of_xlate(struct mbox_controller *mbox,
					      const struct of_phandle_args *sp)
{
	int i;

	if (sp->args_count != 0)
		return ERR_PTR(-EINVAL);

	/*
	 * Return the first available channel. When we don't pass the
	 * channel ID from device tree, each channel populated by the driver is
	 * just a software construct or a virtual channel. We use 'void *data'
	 * in send_data() to pass the channel identifiers.
	 */
	for (i = 0; i < mbox->num_chans; i++)
		if (mbox->chans[i].cl == NULL)
			return &mbox->chans[i];
	return ERR_PTR(-EINVAL);
}

static const struct of_device_id exynos_mbox_match[] = {
	{ .compatible = "google,gs101-mbox", .data = &gs101_mbox_data },
	{ .compatible = "samsung,exynos990-mbox", .data = &exynos990_mbox_data },
	{},
};
MODULE_DEVICE_TABLE(of, exynos_mbox_match);

static int exynos_mbox_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct exynos_mbox *exynos_mbox;
	struct mbox_controller *mbox;
	struct mbox_chan *chans;
	struct clk *pclk;

	exynos_mbox = devm_kzalloc(dev, sizeof(*exynos_mbox), GFP_KERNEL);
	if (!exynos_mbox)
		return -ENOMEM;

	mbox = devm_kzalloc(dev, sizeof(*mbox), GFP_KERNEL);
	if (!mbox)
		return -ENOMEM;

	chans = devm_kcalloc(dev, EXYNOS_MBOX_CHAN_COUNT, sizeof(*chans),
			     GFP_KERNEL);
	if (!chans)
		return -ENOMEM;

	exynos_mbox->data = of_device_get_match_data(dev);
	if (!exynos_mbox->data)
		return dev_err_probe(dev, -EINVAL, "No match data.\n");

	exynos_mbox->regs = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(exynos_mbox->regs))
		return PTR_ERR(exynos_mbox->regs);

	pclk = devm_clk_get_enabled(dev, "pclk");
	if (IS_ERR(pclk))
		return dev_err_probe(dev, PTR_ERR(pclk),
				     "Failed to enable clock.\n");

	mbox->num_chans = EXYNOS_MBOX_CHAN_COUNT;
	mbox->chans = chans;
	mbox->dev = dev;
	mbox->ops = &exynos_mbox_chan_ops;
	mbox->of_xlate = exynos_mbox_of_xlate;

	exynos_mbox->mbox = mbox;

	platform_set_drvdata(pdev, exynos_mbox);

	/* Mask out all interrupts. We support just polling channels for now. */
	writel(EXYNOS_MBOX_INTMR0_MASK,
	       exynos_mbox->regs + exynos_mbox->data->intmr0);
	/*
	 * z3s: also mask the RX-direction (group 1) interrupts so that
	 * interrupt-mode ACPM channels (e.g. CPU DVFS on channel 5) are
	 * delivered in poll mode and serviced by the existing poll path.
	 */
	if (exynos_mbox->data->intmr1)
		writel(EXYNOS_MBOX_INTMR0_MASK,
		       exynos_mbox->regs + exynos_mbox->data->intmr1);

	return devm_mbox_controller_register(dev, mbox);
}

static struct platform_driver exynos_mbox_driver = {
	.probe	= exynos_mbox_probe,
	.driver	= {
		.name = "exynos-acpm-mbox",
		.of_match_table	= exynos_mbox_match,
	},
};
module_platform_driver(exynos_mbox_driver);

MODULE_AUTHOR("Tudor Ambarus <tudor.ambarus@linaro.org>");
MODULE_DESCRIPTION("Samsung Exynos mailbox driver");
MODULE_LICENSE("GPL");
