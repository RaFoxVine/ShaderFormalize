void Set(out float value, float3 ignored = normalize(float3(0.0, 0.0, 0.0)))
{
    value = 1.0;
}
float4 main(float4 a : COLOR0) : SV_Target
{
    float value = 0.0;
    if (a.x <= 0.5)
        Set(value);
    return a + float4(value, 0, 0, 0);
}
