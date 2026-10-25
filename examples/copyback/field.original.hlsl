void Identity(float x, out float y) { y = x; }
float4 main(float4 a : COLOR0) : SV_Target
{
    float value = a.y;
    if (a.x > 0.5)
        Identity(a.y, value);
    return float4(ddx(value), 0, 0, 1);
}
