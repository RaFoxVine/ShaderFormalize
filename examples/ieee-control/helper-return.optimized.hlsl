uint MixWord(uint word, uint key) {
    uint mixed = word + key;
    mixed = mixed - 3u;
    mixed = mixed * 0x85EBCA6Bu;
    mixed = mixed & 0x7FFFFFFFu;
    mixed = mixed | 1u;
    mixed = mixed ^ (mixed >> 13u);
    mixed = mixed << key;
    mixed = mixed >> (key >> 5u);
    uint result = mixed < 0x80000000u ? mixed : mixed ^ 0x9E3779B9u;
    return word == 0u ? key : result;
}

float4 main(float4 input : COLOR0) : SV_Target {
    uint word = MixWord(asuint(input.x), asuint(input.y));
    return word == 0u ? input : float4(asfloat(word), input.y, input.z, input.w);
}
