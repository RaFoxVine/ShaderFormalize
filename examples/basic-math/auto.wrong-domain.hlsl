float4 main(float4 a : COLOR0) : SV_Target
{
    float4 unused = clamp(a, 1.0, 0.0);
    return min(max(a, 0.0), 1.0) * 0.5;
}
