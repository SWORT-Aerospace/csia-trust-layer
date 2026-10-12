// Exhaustive check that the patch's multiplication is an identity at eta = 1.
// For every one of the 2^32 float bit patterns x, compare bits(x * eta) with
// bits(x), where eta = 1.0f is read at run time (volatile), as _mot_eff[i] is in
// the patched Sih::read_motors. Compile with the flags PX4 used for sih.cpp.
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cmath>

int main()
{
	volatile float eta_v = 1.0f;
	const float eta = eta_v;
	uint64_t checked = 0, differ = 0, nan_in = 0, nan_payload_differ = 0;

	for (uint64_t b = 0; b <= 0xFFFFFFFFull; b++) {
		uint32_t xb = static_cast<uint32_t>(b);
		float x;
		std::memcpy(&x, &xb, 4);
		float y = x * eta;
		uint32_t yb;
		std::memcpy(&yb, &y, 4);
		checked++;

		if (std::isnan(x)) {
			nan_in++;
			// signalling NaNs are quietened by any arithmetic; the command path never carries NaN into SIH
			if (yb != xb) { nan_payload_differ++; }

		} else if (yb != xb) {
			differ++;
		}
	}

	std::printf("checked=%llu non_nan_bit_differences=%llu nan_inputs=%llu nan_patterns_changed=%llu\n",
		    (unsigned long long)checked, (unsigned long long)differ,
		    (unsigned long long)nan_in, (unsigned long long)nan_payload_differ);
	return differ == 0 ? 0 : 1;
}
