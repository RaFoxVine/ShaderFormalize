float4 main(float4 a:COLOR0):SV_Target
{
    bool b=a.x<=0.0;
    if(b)discard;
    return float4(normalize(a.yzw),1);
}
