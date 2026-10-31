struct PackedWord { float payload; };
PackedWord StoreFields(float4 input)
{
    uint r = asuint(input.x) & 0xFFu;
    uint g = asuint(input.y) & 0xFFu;
    uint b = asuint(input.z) & 0xFFu;
    uint a = asuint(input.w) & 0xFFu;
    uint word = r | (g << 8u) | (b << 16u) | (a << 24u);
    PackedWord packed;
    packed.payload = asfloat(word);
    return packed;
}
float4 ReadFields(PackedWord packed)
{
    uint word = asuint(packed.payload);
    return float4(asfloat(word & 0xFFu), asfloat((word >> 8u) & 0xFFu),
                  asfloat((word >> 16u) & 0xFFu), asfloat((word >> 24u) & 0xFFu));
}
float4 main(float4 input : COLOR0) : SV_Target
{
    return ReadFields(StoreFields(input));
}
