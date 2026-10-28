float4 main(float a : COLOR0, float b : COLOR1, float c : COLOR2) : SV_Target
{
    float result = a + (b + c);
    return float4(result, result, result, result);
}
