float4 main(float4 a : COLOR0, float t : TEXCOORD0) : SV_Target
{
    return float4(a.x + t, a.y - t, a.z * t, sqrt(a.w / t));
}
