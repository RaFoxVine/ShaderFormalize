uint2 mixPair(uint2 x, uint n) { return (x ^ n) + 1u; }
float4 main(float4 input : COLOR0) : SV_Target {
    uint2 x[2][2];
    x[0][0] = asuint(input.xy); x[0][1] = asuint(input.zw);
    x[1][0] = asuint(input.zw); x[1][1] = asuint(input.xy);
    x[0][0] = mixPair(x[0][0], 0u + 5u);
    x[0][1] = mixPair(x[0][1], 1u + 5u);
    x[1][0] = mixPair(x[1][0], 0u + 9u);
    x[1][1] = mixPair(x[1][1], 1u + 9u);
    return asfloat(uint4(x[0][0] ^ x[1][0], x[0][1] + x[1][1]));
}
