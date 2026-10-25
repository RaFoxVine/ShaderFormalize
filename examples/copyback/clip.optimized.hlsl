float4 main(float4 a : COLOR0) : SV_Target
{
    clip(a.x);
    return float4(a.x * 2.0, a.yzw);
}
