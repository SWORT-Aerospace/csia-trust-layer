/* Negative-input harness for csia_core.c (audit finding F-04).
 *
 * Every case here is an input the C core must REJECT deterministically,
 * without an out-of-bounds access and without mutating carried state.
 * Built and run under ASan + UBSan by csia/native/build.sh --check and by CI;
 * a sanitizer trap is a test failure, not a warning.
 *
 *   cc -std=c11 -Wall -Wextra -Wpedantic -Werror \
 *      -fsanitize=address,undefined -g csia_core.c test_guards.c -lm -o t && ./t
 */

#include <stdio.h>
#include <string.h>

#define CSIA_OK              0
#define CSIA_ERR_NODES      -1
#define CSIA_ERR_EDGES      -2
#define CSIA_ERR_EDGE_INDEX -3
#define CSIA_ERR_NULL       -4
#define CSIA_ERR_CAUSES     -5

int csia_trust_step(int n, int m, const int *ea, const int *eb,
    const double *elam, const double *egate,
    const double *plam, const double *pgate, const unsigned char *phas,
    const double *hist, const unsigned char *hist_has,
    const double *vr, const unsigned char *vr_has,
    const unsigned char *fresh,
    double w_nbr, double w_phys, double w_temp, double w_stat,
    double rho_max, double rho_min,
    double *alpha, double *beta, double *trust,
    double *out_trust, double *out_evidence, double *out_comps);

int csia_diag_step(int nf, int nc, const double *c, const double *gate,
    const unsigned char *low, const double *log_prior,
    double smooth_alpha, double mult, double eps,
    double *smoothed, int *initialized, double *out_post);

static int failures = 0;

static void check(const char *name, int got, int want) {
    if (got != want) {
        printf("FAIL %-38s got %d, want %d\n", name, got, want);
        failures++;
    } else {
        printf("ok   %-38s -> %d\n", name, got);
    }
}

#define N 4
#define M 3

/* Fixture: a valid 4-node / 3-edge tick. Individual cases perturb one input. */
struct fx {
    int ea[M], eb[M];
    double elam[M], egate[M];
    double plam[N], pgate[N];
    unsigned char phas[N], hist_has[N], vr_has[N], fresh[N];
    double hist[N], vr[N];
    double alpha[N], beta[N], trust[N];
    double out_trust[N], out_evidence[N], out_comps[4 * N];
};

static void fx_init(struct fx *f) {
    memset(f, 0, sizeof *f);
    int a[M] = {0, 1, 2}, b[M] = {1, 2, 3};
    for (int e = 0; e < M; e++) {
        f->ea[e] = a[e]; f->eb[e] = b[e];
        f->elam[e] = 1.0; f->egate[e] = 1.0;
    }
    for (int i = 0; i < N; i++) {
        f->plam[i] = 1.0; f->pgate[i] = 1.0;
        f->phas[i] = 1; f->hist_has[i] = 1; f->vr_has[i] = 1; f->fresh[i] = 1;
        f->hist[i] = 1.0; f->vr[i] = 1.0;
        f->alpha[i] = 8.0; f->beta[i] = 2.0; f->trust[i] = 0.8;
    }
}

static int run(struct fx *f, int n, int m) {
    return csia_trust_step(n, m, f->ea, f->eb, f->elam, f->egate,
        f->plam, f->pgate, f->phas, f->hist, f->hist_has, f->vr, f->vr_has,
        f->fresh, 0.35, 0.30, 0.20, 0.15, 0.998, 0.95,
        f->alpha, f->beta, f->trust,
        f->out_trust, f->out_evidence, f->out_comps);
}

/* State must be byte-identical after a rejected call. */
static int state_unchanged(const struct fx *f) {
    for (int i = 0; i < N; i++)
        if (f->alpha[i] != 8.0 || f->beta[i] != 2.0 || f->trust[i] != 0.8)
            return 0;
    return 1;
}

int main(void) {
    struct fx f;

    fx_init(&f);
    check("valid tick", run(&f, N, M), CSIA_OK);

    /* --- count bounds ---------------------------------------------------- */
    fx_init(&f);
    check("n negative", run(&f, -1, M), CSIA_ERR_NODES);
    check("  state untouched", state_unchanged(&f), 1);

    fx_init(&f);
    check("n over CSIA_MAX_NODES", run(&f, 65, M), CSIA_ERR_NODES);
    check("  state untouched", state_unchanged(&f), 1);

    fx_init(&f);
    check("m negative", run(&f, N, -1), CSIA_ERR_EDGES);
    check("  state untouched", state_unchanged(&f), 1);

    fx_init(&f);
    check("m over CSIA_MAX_EDGES", run(&f, N, 513), CSIA_ERR_EDGES);
    check("  state untouched", state_unchanged(&f), 1);

    /* --- edge endpoint validity (the F-04 defect) ------------------------ */
    fx_init(&f);
    f.ea[1] = N;                       /* == n, one past the last node */
    check("edge src == n", run(&f, N, M), CSIA_ERR_EDGE_INDEX);
    check("  state untouched", state_unchanged(&f), 1);

    fx_init(&f);
    f.eb[2] = 9999;                    /* far out of range */
    check("edge dst far out of range", run(&f, N, M), CSIA_ERR_EDGE_INDEX);
    check("  state untouched", state_unchanged(&f), 1);

    fx_init(&f);
    f.ea[0] = -1;
    check("edge src negative", run(&f, N, M), CSIA_ERR_EDGE_INDEX);
    check("  state untouched", state_unchanged(&f), 1);

    fx_init(&f);
    f.eb[0] = -7;
    check("edge dst negative", run(&f, N, M), CSIA_ERR_EDGE_INDEX);

    /* An edge referencing a node beyond a REDUCED n must also be caught:
     * the table is valid for 4 nodes but the caller passed n = 2. */
    fx_init(&f);
    check("edge valid for n=4 but n=2 given", run(&f, 2, M),
          CSIA_ERR_EDGE_INDEX);
    check("  state untouched", state_unchanged(&f), 1);

    /* --- NULL pointers ---------------------------------------------------- */
    fx_init(&f);
    check("NULL edge array with m>0",
          csia_trust_step(N, M, NULL, f.eb, f.elam, f.egate,
              f.plam, f.pgate, f.phas, f.hist, f.hist_has, f.vr, f.vr_has,
              f.fresh, 0.35, 0.30, 0.20, 0.15, 0.998, 0.95,
              f.alpha, f.beta, f.trust,
              f.out_trust, f.out_evidence, f.out_comps), CSIA_ERR_NULL);
    check("  state untouched", state_unchanged(&f), 1);

    fx_init(&f);
    check("NULL trust state",
          csia_trust_step(N, M, f.ea, f.eb, f.elam, f.egate,
              f.plam, f.pgate, f.phas, f.hist, f.hist_has, f.vr, f.vr_has,
              f.fresh, 0.35, 0.30, 0.20, 0.15, 0.998, 0.95,
              f.alpha, f.beta, NULL,
              f.out_trust, f.out_evidence, f.out_comps), CSIA_ERR_NULL);

    fx_init(&f);
    check("NULL output buffer",
          csia_trust_step(N, M, f.ea, f.eb, f.elam, f.egate,
              f.plam, f.pgate, f.phas, f.hist, f.hist_has, f.vr, f.vr_has,
              f.fresh, 0.35, 0.30, 0.20, 0.15, 0.998, 0.95,
              f.alpha, f.beta, f.trust,
              NULL, f.out_evidence, f.out_comps), CSIA_ERR_NULL);

    /* --- degenerate but LEGAL inputs must succeed, not be rejected -------- */
    fx_init(&f);
    check("n=0 (no nodes) is legal", run(&f, 0, 0), CSIA_OK);
    fx_init(&f);
    check("m=0 (no edges) is legal", run(&f, N, 0), CSIA_OK);

    /* --- diagnosis core --------------------------------------------------- */
    {
        double c[2] = {0.9, 0.9}, gate[2] = {1.0, 1.0};
        unsigned char low[2 * 2] = {0, 1, 1, 0};
        double log_prior[2] = {-0.15, -2.0};
        double smoothed[2] = {0.0, 0.0}, post[2] = {0.0, 0.0};
        int init = 0;

        check("diag valid",
              csia_diag_step(2, 2, c, gate, low, log_prior,
                             0.06, 1.5, 1e-9, smoothed, &init, post),
              CSIA_OK);
        check("diag nc over CSIA_MAX_CAUSES",
              csia_diag_step(2, 33, c, gate, low, log_prior,
                             0.06, 1.5, 1e-9, smoothed, &init, post),
              CSIA_ERR_CAUSES);
        check("diag nf negative",
              csia_diag_step(-1, 2, c, gate, low, log_prior,
                             0.06, 1.5, 1e-9, smoothed, &init, post),
              CSIA_ERR_CAUSES);
        check("diag NULL log_prior",
              csia_diag_step(2, 2, c, gate, low, NULL,
                             0.06, 1.5, 1e-9, smoothed, &init, post),
              CSIA_ERR_NULL);
        check("diag NULL feature array with nf>0",
              csia_diag_step(2, 2, NULL, gate, low, log_prior,
                             0.06, 1.5, 1e-9, smoothed, &init, post),
              CSIA_ERR_NULL);
    }

    printf(failures ? "\n%d FAILURE(S)\n" : "\nall guard cases passed\n",
           failures);
    return failures ? 1 : 0;
}
