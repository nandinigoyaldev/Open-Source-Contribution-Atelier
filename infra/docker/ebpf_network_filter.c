// SPDX-License-Identifier: GPL-2.0
/*
 * eBPF cgroup network filter for sandbox containers.
 * Blocks all outbound network traffic except to whitelisted loopback addresses:
 * - IPv4: 127.0.0.0/8 (0x7F000000/8)
 * - IPv6: ::1
 */

#include <linux/bpf.h>
#include <linux/in.h>
#include <linux/in6.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

#define LOOPBACK_IPV4_MASK 0xFF000000
#define LOOPBACK_IPV4_NET  0x7F000000

SEC("cgroup/connect4")
int filter_outbound_ipv4(struct bpf_sock_addr *ctx) {
    __u32 dest_ip = bpf_ntohl(ctx->user_ip4);

    // Whitelist: Loopback addresses (127.0.0.0/8)
    if ((dest_ip & LOOPBACK_IPV4_MASK) == LOOPBACK_IPV4_NET) {
        return 1; // Allow connection
    }

    // Block all non-loopback outbound connections
    return 0; // Reject with -EPERM
}

SEC("cgroup/connect6")
int filter_outbound_ipv6(struct bpf_sock_addr *ctx) {
    // Whitelist: IPv6 Loopback (::1)
    if (ctx->user_ip6[0] == 0 &&
        ctx->user_ip6[1] == 0 &&
        ctx->user_ip6[2] == 0 &&
        ctx->user_ip6[3] == bpf_htonl(1)) {
        return 1; // Allow loopback
    }

    // Block all other IPv6 outbound connections
    return 0; // Reject with -EPERM
}

char _license[] SEC("license") = "GPL";
