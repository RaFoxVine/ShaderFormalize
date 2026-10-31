float4 main(float4 input : COLOR0) : SV_Target
{
    uint word = asuint(input.x);
    uint key = asuint(input.y);
    return float4(asfloat((word + 0xFFFFFFFFu) + 1u), asfloat(-(-word)),
                  asfloat(~(~word)), asfloat((word ^ key) ^ key));
}
