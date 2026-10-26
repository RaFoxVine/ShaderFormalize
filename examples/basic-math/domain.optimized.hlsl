float4 main(float4 a : COLOR0) : SV_Target
{
    if (a.x > 0.0)
        return float4(sqrt(a.x), 1.0 / sqrt(a.x), 1.0 / a.x, a.y / a.x);
    return a;
}
