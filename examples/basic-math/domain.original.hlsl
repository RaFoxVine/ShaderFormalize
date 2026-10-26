float4 main(float4 a : COLOR0) : SV_Target
{
    if (a.x > 0.0)
    {
        float root = sqrt(a.x);
        float inverseRoot = rsqrt(a.x);
        float inverse = rcp(a.x);
        return float4(root, inverseRoot, inverse, a.y / a.x);
    }
    return a;
}
