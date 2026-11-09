// SPDX-License-Identifier: GPL-2.0-only
/*
 * Samsung Exynos 990 Thermal Management Unit (TMU) Driver
 */

#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/of.h>
#include <linux/io.h>
#include <linux/thermal.h>

#define EXYNOS990_TMU_TRIM_BASE      0x10
#define EXYNOS990_TMU_TEMP_BASE      0x84

struct exynos990_tmu;

struct exynos990_tmu_sensor {
	struct exynos990_tmu *tmu;
	int id;
	struct thermal_zone_device *tzd;
};

struct exynos990_tmu {
	struct device *dev;
	void __iomem *base;
	struct exynos990_tmu_sensor sensors[10];
};

static int exynos990_tmu_get_temp(struct thermal_zone_device *tz, int *temp)
{
	struct exynos990_tmu_sensor *sensor = thermal_zone_device_priv(tz);
	struct exynos990_tmu *tmu;
	int id;
	u32 val, trim_val;
	u16 raw, trim;

	if (!sensor || !sensor->tmu)
		return -EINVAL;

	tmu = sensor->tmu;
	id = sensor->id;

	if (id < 0 || id >= 10)
		return -EINVAL;

	/* Read raw temperature: 2 sensors per 32-bit register from 0x84 */
	val = readl(tmu->base + EXYNOS990_TMU_TEMP_BASE + (id / 2) * 4);
	if (id % 2 == 0)
		raw = val & 0xffff;
	else
		raw = (val >> 16) & 0xffff;

	/* Read 2-point calibration trim value from 0x10 + id * 4 */
	trim_val = readl(tmu->base + EXYNOS990_TMU_TRIM_BASE + id * 4);
	trim = trim_val & 0xff;
	u16 delta85 = (trim_val >> 8) & 0xff;

	if (!trim || trim == 0xff)
		trim = 194; /* fallback standard trim at 25C */
	if (!delta85 || delta85 == 0xff)
		delta85 = 114; /* fallback standard delta between 25C and 85C */

	/* 2-point calibration: 25C base + (raw - trim25) * (85 - 25) / delta85 */
	*temp = 25000 + (((int)raw - (int)trim) * 60000) / (int)delta85;

	return 0;
}

static const struct thermal_zone_device_ops exynos990_tmu_ops = {
	.get_temp = exynos990_tmu_get_temp,
};

static int exynos990_tmu_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct exynos990_tmu *tmu;
	int i;

	tmu = devm_kzalloc(dev, sizeof(*tmu), GFP_KERNEL);
	if (!tmu)
		return -ENOMEM;

	tmu->dev = dev;
	tmu->base = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(tmu->base))
		return PTR_ERR(tmu->base);

	platform_set_drvdata(pdev, tmu);

	/* Register thermal zones for all configured sensor channels */
	for (i = 0; i < 10; i++) {
		tmu->sensors[i].tmu = tmu;
		tmu->sensors[i].id = i;
		tmu->sensors[i].tzd = devm_thermal_of_zone_register(dev, i,
							&tmu->sensors[i],
							&exynos990_tmu_ops);
		if (IS_ERR(tmu->sensors[i].tzd)) {
			tmu->sensors[i].tzd = NULL;
		} else {
			dev_info(dev, "Sensor %d registered as thermal zone\n", i);
		}
	}

	dev_info(dev, "Exynos 990 TMU initialized at %pr\n", &pdev->resource[0]);
	return 0;
}

static const struct of_device_id exynos990_tmu_of_match[] = {
	{ .compatible = "samsung,exynos990-tmu" },
	{ }
};
MODULE_DEVICE_TABLE(of, exynos990_tmu_of_match);

static struct platform_driver exynos990_tmu_driver = {
	.driver = {
		.name = "exynos990-tmu",
		.of_match_table = exynos990_tmu_of_match,
	},
	.probe = exynos990_tmu_probe,
};
module_platform_driver(exynos990_tmu_driver);

MODULE_DESCRIPTION("Samsung Exynos 990 Thermal Management Unit Driver");
MODULE_LICENSE("GPL");
