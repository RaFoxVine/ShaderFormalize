float4 main(float4 a:COLOR0):SV_Target
{
    bool keep=a.x>0.5;
    if(!keep)discard;
    return a.y>0.5?a:a*2;
}
