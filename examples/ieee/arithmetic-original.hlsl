float4 main(float4 a : COLOR0, float t : TEXCOORD0) : SV_Target
{
    float x = a.x + t;
    float y = a.y - t;
    float z = a.z * t;
    float w = a.w / t;
    return float4(x, y, z, sqrt(w));
}
