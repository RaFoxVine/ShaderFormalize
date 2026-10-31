uint2 mixPair(uint2 x, uint n) { return (x ^ n) + 1u; }
float4 main(float4 input : COLOR0) : SV_Target {
    uint2 x[2][2];
    x[0][0] = asuint(input.xy); x[0][1] = asuint(input.zw);
    x[1][0] = asuint(input.zw); x[1][1] = asuint(input.xy);
    for (uint i=0u; i<2u; i++) {
        for (uint j=0u; j<2u; ++j) {
            if (i == 0u) { x[i][j] = mixPair(x[i][j], j + 5u); }
            else { x[i][j] = mixPair(x[i][j], j + 9u); }
        }
    }
    return asfloat(uint4(x[0][0] ^ x[1][0], x[0][1] + x[1][1]));
}
