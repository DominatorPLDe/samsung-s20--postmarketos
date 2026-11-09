/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef __EXYNOS_ACPM_H__
#define __EXYNOS_ACPM_H__

#include <linux/types.h>

struct acpm_xfer {
	const u32 *txd;
	u32 *rxd;
	size_t txcnt;
	size_t rxcnt;
	unsigned int acpm_chan_id;
};

struct acpm_handle;

void acpm_set_xfer(struct acpm_xfer *xfer, u32 *cmd, size_t cmdcnt,
		   unsigned int acpm_chan_id, bool response);
int acpm_do_xfer(struct acpm_handle *handle,
		 const struct acpm_xfer *xfer);

#endif /* __EXYNOS_ACPM_H__ */
