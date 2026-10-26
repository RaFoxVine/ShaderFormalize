float4 main(float4 a : COLOR0) : SV_Target
{
    float3 value = a.xyz;
    for (uint i = 0u; i < 0u; ++i)
    {
        value = normalize(float3(0.0, 0.0, 0.0));
    }
    return float4(value, a.w);
}
