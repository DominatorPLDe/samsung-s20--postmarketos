// SPDX-License-Identifier: GPL-2.0-only
/*
 * Exynos990 ACPM cpufreq driver (z3s).
 *
 * Drives the three CPU clusters (CPUCL0/1/2) via the ACPM DVFS channel.
 * ACPM performs the matching voltage transition, so the driver only requests
 * frequencies. get_rate is not reliable on this firmware, so .get returns the
 * cached target. Built as a module for iteration.
 */
#include <linux/cpu.h>
#include <linux/cpufreq.h>
#include <linux/cpu_cooling.h>
#include <linux/err.h>
#include <linux/firmware/samsung/exynos-acpm-protocol.h>
#include <linux/init.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/slab.h>
#include <linux/units.h>

#define ACPM_DVFS_CHANNEL	5

struct z3s_cluster {
	unsigned int acpm_id;		/* CPUCL0=2, CPUCL1=3, CPUCL2=4 */
	unsigned int first_cpu;
	unsigned int last_cpu;
	const unsigned int *khz;	/* ascending frequency table (kHz) */
	unsigned int n;
	unsigned int cur_khz;
	struct thermal_cooling_device *cdev;
};

static const unsigned int cl0_khz[] = {
	442000, 650000, 858000, 1066000, 1274000, 1482000, 1690000, 1898000, 2002000
};
static const unsigned int cl1_khz[] = {
	507000, 693000, 862000, 1063000, 1264000, 1466000, 1670000, 1872000,
	2074000, 2276000, 2478000, 2600000
};
static const unsigned int cl2_khz[] = {
	546000, 754000, 1014000, 1248000, 1456000, 1690000, 1898000, 2106000,
	2340000, 2548000, 2730000
};

static struct z3s_cluster clusters[] = {
	{ 2, 0, 3, cl0_khz, ARRAY_SIZE(cl0_khz), 0 },
	{ 3, 4, 5, cl1_khz, ARRAY_SIZE(cl1_khz), 0 },
	{ 4, 6, 7, cl2_khz, ARRAY_SIZE(cl2_khz), 0 },
};

static struct acpm_handle *z3s_acpm;
static struct platform_device *z3s_pdev;

static struct z3s_cluster *cluster_for_cpu(unsigned int cpu)
{
	unsigned int i;

	for (i = 0; i < ARRAY_SIZE(clusters); i++)
		if (cpu >= clusters[i].first_cpu && cpu <= clusters[i].last_cpu)
			return &clusters[i];
	return NULL;
}

static int z3s_target_index(struct cpufreq_policy *policy, unsigned int index)
{
	struct z3s_cluster *cl = policy->driver_data;
	unsigned int khz = policy->freq_table[index].frequency;
	int ret;

	ret = z3s_acpm->ops->dvfs.set_rate(z3s_acpm, ACPM_DVFS_CHANNEL,
					   cl->acpm_id,
					   (unsigned long)khz * HZ_PER_KHZ);
	if (!ret)
		cl->cur_khz = khz;
	return ret;
}

static unsigned int z3s_get(unsigned int cpu)
{
	struct z3s_cluster *cl = cluster_for_cpu(cpu);

	if (!cl)
		return 0;
	return cl->cur_khz ? cl->cur_khz : cl->khz[cl->n - 1];
}

static int z3s_cpufreq_init(struct cpufreq_policy *policy)
{
	struct z3s_cluster *cl = cluster_for_cpu(policy->cpu);
	struct cpufreq_frequency_table *ft;
	unsigned int i, cpu;

	if (!cl)
		return -ENODEV;

	ft = kcalloc(cl->n + 1, sizeof(*ft), GFP_KERNEL);
	if (!ft)
		return -ENOMEM;
	for (i = 0; i < cl->n; i++)
		ft[i].frequency = cl->khz[i];
	ft[cl->n].frequency = CPUFREQ_TABLE_END;

	/* claim all online siblings in this cluster */
	for (cpu = cl->first_cpu; cpu <= cl->last_cpu; cpu++)
		if (cpu_possible(cpu))
			cpumask_set_cpu(cpu, policy->cpus);

	policy->freq_table = ft;
	policy->driver_data = cl;
	policy->cpuinfo.transition_latency = 2 * NSEC_PER_MSEC;

	/* seed the cache with the top OPP so .get is sane before first switch */
	if (!cl->cur_khz)
		cl->cur_khz = cl->khz[cl->n - 1];

	return 0;
}

static void z3s_cpufreq_ready(struct cpufreq_policy *policy)
{
	struct z3s_cluster *cl = policy->driver_data;

	if (cl && !cl->cdev)
		cl->cdev = of_cpufreq_cooling_register(policy);
}

static void z3s_cpufreq_exit(struct cpufreq_policy *policy)
{
	struct z3s_cluster *cl = policy->driver_data;

	if (cl && cl->cdev) {
		cpufreq_cooling_unregister(cl->cdev);
		cl->cdev = NULL;
	}
	kfree(policy->freq_table);
}

static struct cpufreq_driver z3s_cpufreq_driver = {
	.name		= "exynos990-acpm",
	.flags		= CPUFREQ_NEED_INITIAL_FREQ_CHECK |
			  CPUFREQ_HAVE_GOVERNOR_PER_POLICY,
	.verify		= cpufreq_generic_frequency_table_verify,
	.target_index	= z3s_target_index,
	.get		= z3s_get,
	.init		= z3s_cpufreq_init,
	.exit		= z3s_cpufreq_exit,
	.ready		= z3s_cpufreq_ready,
	.attr		= cpufreq_generic_attr,
};

static int __init z3s_cpufreq_module_init(void)
{
	struct device_node *np;
	int ret;

	z3s_pdev = platform_device_register_simple("exynos990-cpufreq",
						   PLATFORM_DEVID_NONE, NULL, 0);
	if (IS_ERR(z3s_pdev))
		return PTR_ERR(z3s_pdev);

	np = of_find_compatible_node(NULL, NULL, "samsung,exynos990-acpm-ipc");
	if (!np) {
		ret = -ENODEV;
		goto err;
	}
	z3s_acpm = devm_acpm_get_by_node(&z3s_pdev->dev, np);
	of_node_put(np);
	if (IS_ERR(z3s_acpm)) {
		ret = PTR_ERR(z3s_acpm);
		goto err;
	}

	ret = cpufreq_register_driver(&z3s_cpufreq_driver);
	if (ret)
		goto err;

	pr_info("exynos990-cpufreq: registered (ACPM DVFS ch %d)\n",
		ACPM_DVFS_CHANNEL);
	return 0;
err:
	platform_device_unregister(z3s_pdev);
	return ret;
}

static void __exit z3s_cpufreq_module_exit(void)
{
	cpufreq_unregister_driver(&z3s_cpufreq_driver);
	platform_device_unregister(z3s_pdev);
}

module_init(z3s_cpufreq_module_init);
module_exit(z3s_cpufreq_module_exit);
MODULE_DESCRIPTION("Exynos990 ACPM cpufreq driver");
MODULE_LICENSE("GPL");
