uint Quantize(float channel)
{
    return uint(saturate(channel) * 255.0);
}

float4 main(float4 color : COLOR0) : SV_Target
{
    uint red = Quantize(color.x);
    uint green = Quantize(color.y);
    return float4((float)(red & 255u) * 0.00390625,
                  (float)(green & 255u) * 0.00390625, color.z, color.w);
}
