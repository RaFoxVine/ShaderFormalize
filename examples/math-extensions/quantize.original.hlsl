float4 main(float4 a:COLOR0):SV_Target {
    float1 x=a.x;
    float1 recovered=floor(x)+frac(x);
    float1 upper=ceil(a.y);
    return float4(recovered,upper,frac(a.z),floor(a.w));
}
