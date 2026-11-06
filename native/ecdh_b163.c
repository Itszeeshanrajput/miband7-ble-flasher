/*
 * NIST B-163 Curve & Session Derivation for Xiaomi Smart Band 7 (Zepp OS)
 * Exact C implementation matching Gadgetbridge ECDH_B163
 */

#include <stdint.h>
#include <string.h>
#include <stdlib.h>

#define CURVE_DEGREE 163
#define BITVEC_NWORDS 6
#define BITVEC_NBYTES 24

static const uint32_t poly[BITVEC_NWORDS] = {0x000000c9, 0, 0, 0, 0, 0x00000008};
static const uint32_t coeff_b[BITVEC_NWORDS] = {0x4a3205fd, 0x512f7874, 0x1481eb10, 0xb8c953ca, 0x0a601907, 0x00000002};
static const uint32_t base_x[BITVEC_NWORDS] = {0xe8343e36, 0xd4994637, 0xa0991168, 0x86a2d57e, 0xf0eba162, 0x00000003};
static const uint32_t base_y[BITVEC_NWORDS] = {0x797324f1, 0xb11c5c0c, 0xa2cdd545, 0x71a0094f, 0xd51fbc6c, 0};
static const uint32_t base_order[BITVEC_NWORDS] = {0xa4234c33, 0x77e70c12, 0x000292fe, 0, 0, 0x00000004};

static inline int bitvec_get_bit(const uint32_t *x, int idx) {
    return (x[idx / 32] >> (idx & 31)) & 1;
}

static inline void bitvec_clr_bit(uint32_t *x, int idx) {
    x[idx / 32] &= ~(1U << (idx & 31));
}

static inline void bitvec_copy(uint32_t *x, const uint32_t *y) {
    memcpy(x, y, BITVEC_NBYTES);
}

static inline int bitvec_equal(const uint32_t *x, const uint32_t *y) {
    return memcmp(x, y, BITVEC_NBYTES) == 0;
}

static inline int bitvec_is_zero(const uint32_t *x) {
    for (int i = 0; i < BITVEC_NWORDS; ++i) if (x[i] != 0) return 0;
    return 1;
}

static int bitvec_degree(const uint32_t *x) {
    int i = BITVEC_NWORDS * 32;
    int y = BITVEC_NWORDS;
    while (i > 0 && x[--y] == 0) i -= 32;
    if (i != 0) {
        uint32_t mask = 1U << 31;
        while ((x[y] & mask) == 0) {
            mask >>= 1;
            i -= 1;
        }
    }
    return i;
}

static void bitvec_lshift(uint32_t *x, const uint32_t *y, int nbits) {
    int nwords = nbits / 32;
    nbits %= 32;
    for (int i = BITVEC_NWORDS - 1; i >= 0; --i) {
        uint32_t w = 0;
        if (i >= nwords) {
            w = y[i - nwords] << nbits;
            if (nbits != 0 && (i - nwords - 1) >= 0) {
                w |= y[i - nwords - 1] >> (32 - nbits);
            }
        }
        x[i] = w;
    }
}

static void gf2field_add(uint32_t *z, const uint32_t *x, const uint32_t *y) {
    for (int i = 0; i < BITVEC_NWORDS; ++i) z[i] = x[i] ^ y[i];
}

static void gf2field_mul(uint32_t *z, const uint32_t *x, const uint32_t *y) {
    uint32_t tmp[BITVEC_NWORDS];
    memset(z, 0, BITVEC_NBYTES);
    for (int i = CURVE_DEGREE - 1; i >= 0; --i) {
        int h = bitvec_get_bit(z, CURVE_DEGREE - 1);
        bitvec_lshift(tmp, z, 1);
        if (h) gf2field_add(z, tmp, poly);
        else bitvec_copy(z, tmp);
        if (bitvec_get_bit(y, i)) {
            gf2field_add(tmp, z, x);
            bitvec_copy(z, tmp);
        }
    }
}

static void gf2field_inv(uint32_t *z, const uint32_t *x) {
    uint32_t u[BITVEC_NWORDS], v[BITVEC_NWORDS], g1[BITVEC_NWORDS], g2[BITVEC_NWORDS];
    uint32_t tmp[BITVEC_NWORDS];
    bitvec_copy(u, x);
    bitvec_copy(v, poly);
    memset(g1, 0, BITVEC_NBYTES); g1[0] = 1;
    memset(g2, 0, BITVEC_NBYTES);
    while (1) {
        int deg_u = bitvec_degree(u);
        int deg_v = bitvec_degree(v);
        if (deg_u < deg_v) {
            uint32_t swp[BITVEC_NWORDS];
            bitvec_copy(swp, u); bitvec_copy(u, v); bitvec_copy(v, swp);
            bitvec_copy(swp, g1); bitvec_copy(g1, g2); bitvec_copy(g2, swp);
            deg_u = bitvec_degree(u); deg_v = bitvec_degree(v);
        }
        if (deg_u == 0) break;
        int j = deg_u - deg_v;
        bitvec_lshift(tmp, v, j); gf2field_add(u, u, tmp);
        bitvec_lshift(tmp, g2, j); gf2field_add(g1, g1, tmp);
    }
    bitvec_copy(z, g2);
}

static void gf2point_double(uint32_t *rx, uint32_t *ry, const uint32_t *px, const uint32_t *py);

static void gf2point_add(uint32_t *rx, uint32_t *ry, const uint32_t *p1x, const uint32_t *p1y, const uint32_t *p2x, const uint32_t *p2y) {
    if (bitvec_equal(p1x, p2x) && bitvec_equal(p1y, p2y)) {
        gf2point_double(rx, ry, p1x, p1y);
        return;
    }
    uint32_t lmb[BITVEC_NWORDS], dx[BITVEC_NWORDS], dy[BITVEC_NWORDS];
    gf2field_add(dx, p1x, p2x);
    gf2field_add(dy, p1y, p2y);
    gf2field_inv(lmb, dx);
    gf2field_mul(lmb, lmb, dy);

    uint32_t t1[BITVEC_NWORDS], t2[BITVEC_NWORDS];
    gf2field_mul(t1, lmb, lmb);
    gf2field_add(t1, t1, lmb);
    gf2field_add(t1, t1, dx);
    bitvec_copy(rx, t1);

    gf2field_add(t2, p1x, rx);
    gf2field_mul(t2, t2, lmb);
    gf2field_add(t2, t2, rx);
    gf2field_add(ry, t2, p1y);
}

static void gf2point_double(uint32_t *rx, uint32_t *ry, const uint32_t *px, const uint32_t *py) {
    if (bitvec_is_zero(px)) {
        memset(rx, 0, BITVEC_NBYTES);
        memset(ry, 0, BITVEC_NBYTES);
        return;
    }
    uint32_t lmb[BITVEC_NWORDS], inv_x[BITVEC_NWORDS];
    gf2field_inv(inv_x, px);
    gf2field_mul(lmb, py, inv_x);
    gf2field_add(lmb, lmb, px);

    uint32_t t1[BITVEC_NWORDS];
    gf2field_mul(t1, lmb, lmb);
    gf2field_add(t1, t1, lmb);
    gf2field_add(rx, t1, coeff_b);

    uint32_t t2[BITVEC_NWORDS];
    gf2field_mul(t2, px, px);
    gf2field_mul(t1, lmb, rx);
    gf2field_add(t1, t1, rx);
    gf2field_add(ry, t1, t2);
}

static void gf2point_mul(uint32_t *rx, uint32_t *ry, const uint32_t *px, const uint32_t *py, const uint32_t *exp) {
    uint32_t tx[BITVEC_NWORDS] = {0}, ty[BITVEC_NWORDS] = {0};
    uint32_t bx[BITVEC_NWORDS], by[BITVEC_NWORDS];
    bitvec_copy(bx, px);
    bitvec_copy(by, py);
    int deg = bitvec_degree(exp);
    for (int i = 0; i < deg; ++i) {
        if (bitvec_get_bit(exp, i)) {
            if (bitvec_is_zero(tx) && bitvec_is_zero(ty)) {
                bitvec_copy(tx, bx);
                bitvec_copy(ty, by);
            } else {
                uint32_t nx[BITVEC_NWORDS], ny[BITVEC_NWORDS];
                gf2point_add(nx, ny, tx, ty, bx, by);
                bitvec_copy(tx, nx);
                bitvec_copy(ty, ny);
            }
        }
        uint32_t nx[BITVEC_NWORDS], ny[BITVEC_NWORDS];
        gf2point_double(nx, ny, bx, by);
        bitvec_copy(bx, nx);
        bitvec_copy(by, ny);
    }
    bitvec_copy(rx, tx);
    bitvec_copy(ry, ty);
}

static void bytes_to_int(const uint8_t *bytes, uint32_t *words) {
    for (int i = 0; i < BITVEC_NWORDS; ++i) {
        words[i] = ((uint32_t)bytes[i*4]) |
                   (((uint32_t)bytes[i*4+1]) << 8) |
                   (((uint32_t)bytes[i*4+2]) << 16) |
                   (((uint32_t)bytes[i*4+3]) << 24);
    }
}

static void ints_to_bytes(const uint32_t *words, uint8_t *bytes) {
    for (int i = 0; i < BITVEC_NWORDS; ++i) {
        bytes[i*4]   = (uint8_t)(words[i] & 0xff);
        bytes[i*4+1] = (uint8_t)((words[i] >> 8) & 0xff);
        bytes[i*4+2] = (uint8_t)((words[i] >> 16) & 0xff);
        bytes[i*4+3] = (uint8_t)((words[i] >> 24) & 0xff);
    }
}

int ecdh_generate_public(const uint8_t *prv_bytes, uint8_t *pub_bytes) {
    uint32_t exp[BITVEC_NWORDS];
    bytes_to_int(prv_bytes, exp);
    if (bitvec_degree(exp) < (CURVE_DEGREE / 2)) return 0;
    int nbits = bitvec_degree(base_order);
    for (int i = nbits - 1; i < BITVEC_NWORDS * 32; ++i) bitvec_clr_bit(exp, i);
    uint32_t rx[BITVEC_NWORDS], ry[BITVEC_NWORDS];
    gf2point_mul(rx, ry, base_x, base_y, exp);
    ints_to_bytes(rx, pub_bytes);
    ints_to_bytes(ry, pub_bytes + BITVEC_NBYTES);
    return 1;
}

int ecdh_shared_secret(const uint8_t *prv_bytes, const uint8_t *remote_pub_bytes, uint8_t *shared_bytes) {
    uint32_t exp[BITVEC_NWORDS];
    bytes_to_int(prv_bytes, exp);
    uint32_t ox[BITVEC_NWORDS], oy[BITVEC_NWORDS];
    bytes_to_int(remote_pub_bytes, ox);
    bytes_to_int(remote_pub_bytes + BITVEC_NBYTES, oy);
    int nbits = bitvec_degree(base_order);
    for (int i = nbits - 1; i < BITVEC_NWORDS * 32; ++i) bitvec_clr_bit(exp, i);
    uint32_t rx[BITVEC_NWORDS], ry[BITVEC_NWORDS];
    gf2point_mul(rx, ry, ox, oy, exp);
    ints_to_bytes(rx, shared_bytes);
    ints_to_bytes(ry, shared_bytes + BITVEC_NBYTES);
    return 1;
}
