uint Ignore(uint value) { return 7u; }

float4 main(float4 a : COLOR0) : SV_Target
{
    uint value = Ignore((uint)(a.x - 2.0));
    return float4((float)value, 9.0, 0, 1);
}
