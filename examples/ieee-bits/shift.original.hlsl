float4 main(float4 input : COLOR0) : SV_Target
{
    uint word = asuint(input.x);
    uint count = asuint(input.y);
    return float4(asfloat(word << count), asfloat(word >> count), input.z, input.w);
}
