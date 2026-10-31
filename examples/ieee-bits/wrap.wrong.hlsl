float4 main(float4 input : COLOR0) : SV_Target
{
    float restored = asfloat(asuint(input.x) + 1u);
    return float4(restored, restored, restored, restored);
}
