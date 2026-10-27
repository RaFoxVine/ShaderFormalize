float4 main(float4 a:COLOR0):SV_Target {
    return float4(a.x,-floor(-a.y),a.z-floor(a.z),floor(a.w));
}
