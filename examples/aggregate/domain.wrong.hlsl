float Read(float values[2], uint index) { return values[index]; }
float4 main(float4 a : COLOR0) : SV_Target
{
    float values[2] = {2.0, 3.0};
    return float4(Read(values, 2u), 0.0, 0.0, 1.0);
}
