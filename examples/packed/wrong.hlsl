uint Quantize(float channel)
{
    return uint(saturate(channel) * 255.0);
}

float4 main(float4 color : COLOR0) : SV_Target
{
    uint red = Quantize(color.x);
    uint green = Quantize(color.y);
    uint packed = (red & 255u) | ((green & 255u) << 7u);
    return float4((float)(packed & 255u) * 0.00390625,
                  (float)((packed >> 8u) & 255u) * 0.00390625, color.z, color.w);
}
