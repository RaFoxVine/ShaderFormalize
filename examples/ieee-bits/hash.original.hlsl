uint HashWord(uint word, uint seed)
{
    uint h = (word ^ seed) + 0x9E3779B9u;
    h = h * 0x85EBCA6Bu;
    h = h ^ (h >> 13u);
    h = h * 0xC2B2AE35u;
    return h ^ (h >> 16u);
}
float4 main(float4 input : COLOR0) : SV_Target
{
    uint h = HashWord(asuint(input.x), asuint(input.y));
    return float4(asfloat(h), input.y, input.z, input.w);
}
