/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef __EXYNOS_ACPM_DVFS_H__
#define __EXYNOS_ACPM_DVFS_H__

int acpm_dvfs_set_rate(struct acpm_handle *handle,
		       unsigned int acpm_chan_id, unsigned int clk_id,
		       unsigned long rate);
unsigned long acpm_dvfs_get_rate(struct acpm_handle *handle,
				 unsigned int acpm_chan_id, unsigned int clk_id);

#endif
