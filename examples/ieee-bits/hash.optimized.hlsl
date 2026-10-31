float4 main(float4 input : COLOR0) : SV_Target
{
    uint h0 = (asuint(input.x) ^ asuint(input.y)) + 0x9E3779B9u;
    uint h1 = h0 * 0x85EBCA6Bu;
    uint h2 = h1 ^ (h1 >> 13u);
    uint h3 = h2 * 0xC2B2AE35u;
    return float4(asfloat(h3 ^ (h3 >> 16u)), input.yzw);
}
