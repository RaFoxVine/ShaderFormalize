float4 main(float4 a : COLOR0, float4 b : COLOR1, float t : TEXCOORD0) : SV_Target
{
    return lerp(a, b, saturate(t));
}
