uint first(uint left, uint right, uint selector) {
    uint result;
    if (selector < 0x80000000u) { result = right; } else { result = left; }
    return result;
}
float4 main(float4 input : COLOR0) : SV_Target {
    uint a = asuint(input.x);
    uint b = asuint(input.y);
    uint c = asuint(input.z);
    uint d = asuint(input.w);
    uint r0 = first(a, b, d);
    uint r1 = a ^ d;
    return float4(asfloat(r0 + 3u), asfloat(r1 + 3u), asfloat(d + 3u), asfloat(c + 3u));
}
