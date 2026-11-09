/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef __EXYNOS_ACPM_TMU_H__
#define __EXYNOS_ACPM_TMU_H__

static inline int acpm_tmu_init(struct acpm_handle *handle, unsigned int chan) { return -EOPNOTSUPP; }
static inline int acpm_tmu_read_temp(struct acpm_handle *handle, unsigned int chan, u8 tz, int *temp) { return -EOPNOTSUPP; }
static inline int acpm_tmu_set_threshold(struct acpm_handle *handle, unsigned int chan, u8 tz, const u8 t[8], size_t len) { return -EOPNOTSUPP; }
static inline int acpm_tmu_set_interrupt_enable(struct acpm_handle *handle, unsigned int chan, u8 tz, u8 en) { return -EOPNOTSUPP; }
static inline int acpm_tmu_tz_control(struct acpm_handle *handle, unsigned int chan, u8 tz, bool en) { return -EOPNOTSUPP; }
static inline int acpm_tmu_clear_tz_irq(struct acpm_handle *handle, unsigned int chan, u8 tz) { return -EOPNOTSUPP; }
static inline int acpm_tmu_suspend(struct acpm_handle *handle, unsigned int chan) { return -EOPNOTSUPP; }
static inline int acpm_tmu_resume(struct acpm_handle *handle, unsigned int chan) { return -EOPNOTSUPP; }

#endif
