/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef __EXYNOS_ACPM_PMIC_H__
#define __EXYNOS_ACPM_PMIC_H__

int acpm_pmic_read_reg(struct acpm_handle *handle, unsigned int acpm_chan_id,
		       u8 type, u8 reg, u8 chan, u8 *buf);
int acpm_pmic_bulk_read(struct acpm_handle *handle, unsigned int acpm_chan_id,
			u8 type, u8 reg, u8 chan, u8 count, u8 *buf);
int acpm_pmic_write_reg(struct acpm_handle *handle, unsigned int acpm_chan_id,
			u8 type, u8 reg, u8 chan, u8 value);
int acpm_pmic_bulk_write(struct acpm_handle *handle, unsigned int acpm_chan_id,
			 u8 type, u8 reg, u8 chan, u8 count, const u8 *buf);
int acpm_pmic_update_reg(struct acpm_handle *handle, unsigned int acpm_chan_id,
			 u8 type, u8 reg, u8 chan, u8 value, u8 mask);

#endif
