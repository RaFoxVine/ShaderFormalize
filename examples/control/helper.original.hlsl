float Identity(float x) { return x; }

float4 main(float4 a : COLOR0) : SV_Target
{
    if (a.x > 0.5)
        return float4(ddx(Identity(a.y)), 0, 0, 1);
    return a;
}
