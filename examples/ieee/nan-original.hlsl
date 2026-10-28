float4 main(float a : COLOR0) : SV_Target
{
    float result = (a == a) ? 1.0 : 0.0;
    return float4(result, result, result, result);
}
