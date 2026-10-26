float4 main(float4 a : COLOR0) : SV_Target
{
    return clamp(a, 0.0, 1.0) / 2.0;
}
