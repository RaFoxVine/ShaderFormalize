float4 main(float4 input : COLOR0) : SV_Target
{
    uint x = asuint(input.x);
    uint y = asuint(input.y);
    uint low = x < y ? x : y;
    bool pick = x < 0x80000000u ? !(x == y) : !(x != y);
    return float4(asfloat(pick ? low : ~low), input.yzw);
}
