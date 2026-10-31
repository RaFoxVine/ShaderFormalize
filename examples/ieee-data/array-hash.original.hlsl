float4 main(float4 input : COLOR0) : SV_Target {
    uint x[4] = {asuint(input.x), asuint(input.y), asuint(input.z), asuint(input.w)};
    [unroll] for (uint i=0u; i<4u; ++i) { x[i] = (x[i] * 3u) ^ (i + 7u); }
    return asfloat(uint4(x[0], x[1], x[2], x[3]));
}
