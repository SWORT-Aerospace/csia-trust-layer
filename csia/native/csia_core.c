/* CSIA native core — the per-tick trust + diagnosis mathematics in C.
 *
 * This is the embeddable kernel: no allocation, no libc beyond math.h,
 * fixed-size state owned by the caller. It is the exact algorithm of
 * csia/trust_engine/engine.py::TrustCore.step and
 * csia/diagnosis/bayes.py::DiagnosisCore.step, and the Python test suite
 * pins the two implementations together to float tolerance.
 *
 * Target contexts: Pi 5 companion (via ctypes, see native/__init__.py) and
 * the STM32H743 flight controller (compile this file directly; ~500 bytes
 * of state for 8 nodes / 12 edges / 8 causes).
 */

#include <math.h>

static double consistency(double lam) {
    double ex = lam - 1.0;
    return ex > 0.0 ? exp(-0.5 * ex) : 1.0;
}

/* One trust tick. Arrays sized: nodes n, edges m.
 * comps out layout: [nbr, phys, temp, stat] per node, -1.0 = unavailable.
 * Returns nothing; alpha/beta/trust are state carried between ticks. */
void csia_trust_step(
    int n, int m,
    const int *ea, const int *eb,
    const double *elam, const double *egate,
    const double *plam, const double *pgate, const unsigned char *phas,
    const double *hist, const unsigned char *hist_has,
    const double *vr, const unsigned char *vr_has,
    const unsigned char *fresh,
    double w_nbr, double w_phys, double w_temp, double w_stat,
    double rho_max, double rho_min,
    double *alpha, double *beta, double *trust,
    double *out_trust, double *out_evidence, double *out_comps)
{
    double new_trust[64];
    for (int i = 0; i < n; i++) {
        double num = 0.0, den = 0.0;
        for (int e = 0; e < m; e++) {
            int other;
            if (ea[e] == i) other = eb[e];
            else if (eb[e] == i) other = ea[e];
            else continue;
            double w = egate[e] * trust[other];
            if (w <= 1e-6) continue;
            num += w * consistency(elam[e]);
            den += w;
        }
        double c_nbr = den > 1e-6 ? num / den : -1.0;
        double c_phys = (phas[i] && pgate[i] > 1e-6)
                        ? consistency(plam[i]) : -1.0;
        double c_temp = hist_has[i] ? consistency(hist[i]) : -1.0;
        double c_stat = vr_has[i] ? consistency(vr[i]) : -1.0;

        double ws[4] = {w_nbr, w_phys, w_temp, w_stat};
        double cs[4] = {c_nbr, c_phys, c_temp, c_stat};
        double wsum = 0.0, esum = 0.0, cmin = 2.0, cmax = -2.0;
        int navail = 0;
        for (int j = 0; j < 4; j++) {
            if (cs[j] < 0.0) continue;
            wsum += ws[j];
            esum += ws[j] * cs[j];
            if (cs[j] < cmin) cmin = cs[j];
            if (cs[j] > cmax) cmax = cs[j];
            navail++;
        }
        double evidence = wsum > 0.0 ? esum / wsum : 0.5;
        double d = navail > 1 ? (cmax - cmin) : 0.0;
        double rho = rho_max - (rho_max - rho_min) * d;

        /* no evidence sources at all -> hold the Beta belief (absence of
         * evidence is absence, not 0.5-consistent); 0.5 is only the
         * reported placeholder. Mirrors engine.py::TrustCore.step. */
        if (fresh[i] && wsum > 0.0) {
            alpha[i] = rho * alpha[i] + evidence;
            beta[i]  = rho * beta[i] + (1.0 - evidence);
        }
        new_trust[i] = alpha[i] / (alpha[i] + beta[i]);
        out_trust[i] = new_trust[i];
        out_evidence[i] = evidence;
        out_comps[4 * i + 0] = c_nbr;
        out_comps[4 * i + 1] = c_phys;
        out_comps[4 * i + 2] = c_temp;
        out_comps[4 * i + 3] = c_stat;
    }
    /* synchronous update: all nodes saw last tick's trust during this step */
    for (int i = 0; i < n; i++) trust[i] = new_trust[i];
}

/* One diagnosis tick. nf features, nc causes.
 * low: nc x nf, 1 where the cause expects that feature LOW.
 * smoothed: nc state carried between ticks (init flag via *initialized). */
void csia_diag_step(
    int nf, int nc,
    const double *c, const double *gate,
    const unsigned char *low,
    const double *log_prior, double smooth_alpha, double mult, double eps,
    double *smoothed, int *initialized,
    double *out_post)
{
    double ll[32];
    for (int k = 0; k < nc; k++) ll[k] = 0.0;
    for (int f = 0; f < nf; f++) {
        if (gate[f] <= 1e-9) continue;
        double lo = log(1.0 - c[f] + eps);
        double hi = log(c[f] + eps);
        for (int k = 0; k < nc; k++)
            ll[k] += gate[f] * (low[k * nf + f] ? lo : hi);
    }
    if (!*initialized) {
        for (int k = 0; k < nc; k++) smoothed[k] = ll[k];
        *initialized = 1;
    } else {
        for (int k = 0; k < nc; k++)
            smoothed[k] = (1.0 - smooth_alpha) * smoothed[k]
                          + smooth_alpha * ll[k];
    }
    double best = -1e300;
    for (int k = 0; k < nc; k++) {
        out_post[k] = log_prior[k] + mult * smoothed[k];
        if (out_post[k] > best) best = out_post[k];
    }
    double sum = 0.0;
    for (int k = 0; k < nc; k++) { out_post[k] = exp(out_post[k] - best);
                                   sum += out_post[k]; }
    for (int k = 0; k < nc; k++) out_post[k] /= sum;
}
