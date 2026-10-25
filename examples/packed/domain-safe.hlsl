float4 main(float4 a : COLOR0) : SV_Target
{
    uint value = a.x > 0.5 ? (uint)(a.x - 2.0) : 7u;
    uint shift = a.y > 0.5 ? (1u << 32u) : 9u;
    return float4((float)value, (float)shift, 0, 1);
}
