struct Channels { uint red; uint green; };

uint Quantize(float channel)
{
    return (uint)(saturate(channel) * 255.0);
}

uint Pack(Channels channels)
{
    return (channels.red & 0xffu) | ((channels.green & 0xffu) << 8u);
}

float4 main(float4 color : COLOR0) : SV_Target
{
    Channels channels;
    channels.red = Quantize(color.x);
    channels.green = Quantize(color.y);
    uint packed = Pack(channels);
    float carrier = asfloat(packed);
    float copy = carrier;
    uint recovered = asuint(copy);
    float red = (float)(recovered & 255u);
    float green = (float)((recovered >> 8u) & 255u);
    return float4(red * 0.00390625, green * 0.00390625, color.z, color.w);
}
