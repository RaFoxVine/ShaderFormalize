float4 main(float4 a : COLOR0) : SV_Target
{
    float root = sqrt(a.x);
    float inverseRoot = rsqrt(a.x);
    float inverse = rcp(a.x);
    if (a.x > 0.0)
        return float4(root, inverseRoot, inverse, a.y / a.x);
    return a;
}
