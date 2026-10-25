void Scale(float input, out float value)
{
    clip(input);
    value = input * 2.0;
}
float4 main(float4 a : COLOR0) : SV_Target
{
    float value;
    Scale(a.x, value);
    return float4(value, a.yzw);
}
