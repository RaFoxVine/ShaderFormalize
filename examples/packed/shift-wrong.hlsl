float4 main(float4 a : COLOR0) : SV_Target
{
    uint value = 1u << 32u;
    return float4(7.0, (float)value, 0, 1);
}
