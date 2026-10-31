float4 main(float4 input : COLOR0) : SV_Target {
    uint x[4] = {asuint(input.x), asuint(input.y), asuint(input.z), asuint(input.w)};
    x[0] = (x[0] * 3u) ^ (0u + 7u);
x[1] = (x[1] * 3u) ^ (1u + 7u);
x[2] = (x[2] * 3u) ^ (2u + 7u);
x[3] = (x[3] * 3u) ^ (3u + 7u);
    return asfloat(uint4(x[0], x[1], x[2], x[3]));
}
