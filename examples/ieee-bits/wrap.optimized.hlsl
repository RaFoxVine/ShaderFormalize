float4 main(float4 input : COLOR0) : SV_Target
{
    float restored = asfloat(asuint(input.x));
    return float4(restored, restored, restored, restored);
}
