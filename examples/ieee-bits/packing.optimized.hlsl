float4 main(float4 input : COLOR0) : SV_Target
{
    return float4(asfloat(asuint(input.x) & 0xFFu), asfloat(asuint(input.y) & 0xFFu),
                  asfloat(asuint(input.z) & 0xFFu), asfloat(asuint(input.w) & 0xFFu));
}
