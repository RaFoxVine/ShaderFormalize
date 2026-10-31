float4 main(float4 input : COLOR0) : SV_Target
{
    return float4(input.y, input.x, input.z, input.w);
}
