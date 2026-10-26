float4 main(float4 a : COLOR0) : SV_Target
{
    float values[2] = {a.y, a.z};
    if (a.x > 0.5) values[0] = a.y;
    return float4(ddx(values[0]), 0.0, 0.0, 1.0);
}
