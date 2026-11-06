# -*- coding: utf-8 -*-
# Archive.org 公开影视（Python 蜘蛛 · 离线目录版）
# 目录数据来自 archive.org 官方公开接口（公有领域 / CC 开放授权作品），
# 已内嵌在本文件中：列表、分类、搜索、详情均不访问网络，
# 只有实际播放时才连接 archive.org 下载地址。
from base.spider import Spider as BaseSpider

CATALOG = [
 {
  "vod_id": "vietnam-travel-guide-hanoi-ha-long-bay-ho-chi-minh-1_202101",
  "vod_name": "Vietnam Travel Guide Hanoi, Ha Long Bay, Ho Chi Minh 1",
  "vod_pic": "https://archive.org/download/vietnam-travel-guide-hanoi-ha-long-bay-ho-chi-minh-1_202101/__ia_thumb.jpg",
  "vod_year": "",
  "vod_remarks": "开放电影",
  "type_id": "opensource_movies",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/vietnam-travel-guide-hanoi-ha-long-bay-ho-chi-minh-1_202101/Vietnam%20Travel%20Guide_%20Hanoi%2C%20Ha%20Long%20Bay%2C%20Ho%20Chi%20Minh1.mp4#备选1$https://archive.org/download/vietnam-travel-guide-hanoi-ha-long-bay-ho-chi-minh-1_202101/Vietnam%20Travel%20Guide_%20Hanoi%2C%20Ha%20Long%20Bay%2C%20Ho%20Chi%20Minh1.ia.mp4"
 },
 {
  "vod_id": "vietnam-travel-guide-hanoi-ha-long-bay-ho-chi-minh_202012",
  "vod_name": "Vietnam Travel Guide Hanoi, Ha Long Bay, Ho Chi Minh",
  "vod_pic": "https://archive.org/download/vietnam-travel-guide-hanoi-ha-long-bay-ho-chi-minh_202012/__ia_thumb.jpg",
  "vod_year": "",
  "vod_remarks": "开放电影",
  "type_id": "opensource_movies",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/vietnam-travel-guide-hanoi-ha-long-bay-ho-chi-minh_202012/Vietnam%20Travel%20Guide_%20Hanoi%2C%20Ha%20Long%20Bay%2C%20Ho%20Chi%20Minh.mp4#备选1$https://archive.org/download/vietnam-travel-guide-hanoi-ha-long-bay-ho-chi-minh_202012/Vietnam%20Travel%20Guide_%20Hanoi%2C%20Ha%20Long%20Bay%2C%20Ho%20Chi%20Minh.ia.mp4"
 },
 {
  "vod_id": "pmovie-20hin_20221006",
  "vod_name": "PMovie 20hin",
  "vod_pic": "https://archive.org/download/pmovie-20hin_20221006/PTM%20-%20ICY.jpg",
  "vod_year": "",
  "vod_remarks": "开放电影",
  "type_id": "opensource_movies",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/pmovie-20hin_20221006/PMovie20hin.mkv#备选1$https://archive.org/download/pmovie-20hin_20221006/%28M%29PMovie20.mkv#备选2$https://archive.org/download/pmovie-20hin_20221006/%28L%29PMovie20.mkv#备选3$https://archive.org/download/pmovie-20hin_20221006/%28B%29PMovie20.mkv#备选4$https://archive.org/download/pmovie-20hin_20221006/PMovie20trlr.mkv"
 },
 {
  "vod_id": "ps-19trlr",
  "vod_name": "PS 19trlr",
  "vod_pic": "https://archive.org/download/ps-19trlr/PS19.jpg",
  "vod_year": "",
  "vod_remarks": "开放电影",
  "type_id": "opensource_movies",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/ps-19trlr/PS19trlr.mkv"
 },
 {
  "vod_id": "sex_madness",
  "vod_name": "Sex Madness",
  "vod_pic": "https://archive.org/download/sex_madness/__ia_thumb.jpg",
  "vod_year": "1938",
  "vod_remarks": "公有领域长片",
  "type_id": "feature_films",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/sex_madness/sex_madness.mp4#备选1$https://archive.org/download/sex_madness/sex_madness_512kb.mp4#备选2$https://archive.org/download/sex_madness/sex_madness.ogv"
 },
 {
  "vod_id": "charlie_chaplin_film_fest",
  "vod_name": "Charlie Chaplin Festival",
  "vod_pic": "https://archive.org/download/charlie_chaplin_film_fest/__ia_thumb.jpg",
  "vod_year": "1938",
  "vod_remarks": "公有领域长片",
  "type_id": "feature_films",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/charlie_chaplin_film_fest/charlie_chaplin_film_fest.mp4#备选1$https://archive.org/download/charlie_chaplin_film_fest/charlie_chaplin_film_fest_512kb.mp4#备选2$https://archive.org/download/charlie_chaplin_film_fest/charlie_chaplin_film_fest.ogv"
 },
 {
  "vod_id": "TheFastandtheFuriousJohnIreland1954goofyrip",
  "vod_name": "The Fast And The Furious",
  "vod_pic": "https://archive.org/download/TheFastandtheFuriousJohnIreland1954goofyrip/TheFastandtheFuriousJohnIreland1954goofyrip.thumbs/TheFastandtheFuriousJohnIreland1954goofyrip_000001.jpg",
  "vod_year": "1955",
  "vod_remarks": "公有领域长片",
  "type_id": "feature_films",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/TheFastandtheFuriousJohnIreland1954goofyrip/TheFastandtheFuriousJohnIreland1954goofyrip.mp4#备选1$https://archive.org/download/TheFastandtheFuriousJohnIreland1954goofyrip/TheFastandtheFuriousJohnIreland1954goofyrip_512kb.mp4#备选2$https://archive.org/download/TheFastandtheFuriousJohnIreland1954goofyrip/TheFastandtheFuriousJohnIreland1954goofyrip.ogv"
 },
 {
  "vod_id": "Dr.Sex",
  "vod_name": "Dr. Sex.",
  "vod_pic": "https://archive.org/download/Dr.Sex/Dr.Sex.thumbs/Dr.Sex_000001.jpg",
  "vod_year": "",
  "vod_remarks": "公有领域长片",
  "type_id": "feature_films",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/Dr.Sex/Dr.Sex.mp4#备选1$https://archive.org/download/Dr.Sex/Dr.Sex.ogv"
 },
 {
  "vod_id": "his_girl_friday",
  "vod_name": "His Girl Friday",
  "vod_pic": "https://archive.org/download/his_girl_friday/__ia_thumb.jpg",
  "vod_year": "1940",
  "vod_remarks": "公有领域长片",
  "type_id": "feature_films",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/his_girl_friday/his_girl_friday.mp4#备选1$https://archive.org/download/his_girl_friday/his_girl_friday_512kb.mp4#备选2$https://archive.org/download/his_girl_friday/his_girl_friday.ogv"
 },
 {
  "vod_id": "VoyagetothePlanetofPrehistoricWomen",
  "vod_name": "Voyage to the Planet of Prehistoric Women",
  "vod_pic": "https://archive.org/download/VoyagetothePlanetofPrehistoricWomen/VoyagetothePlanetofPrehistoricWomen.png",
  "vod_year": "1967",
  "vod_remarks": "公有领域长片",
  "type_id": "feature_films",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/VoyagetothePlanetofPrehistoricWomen/VoyagetothePlanetofPrehistoricWomen.mp4#备选1$https://archive.org/download/VoyagetothePlanetofPrehistoricWomen/VoyagetothePlanetofPrehistoricWomen_512kb.mp4#备选2$https://archive.org/download/VoyagetothePlanetofPrehistoricWomen/VoyagetothePlanetofPrehistoricWomen.ogv"
 },
 {
  "vod_id": "house_on_haunted_hill_ipod",
  "vod_name": "House on Haunted Hill",
  "vod_pic": "https://archive.org/download/house_on_haunted_hill_ipod/__ia_thumb.jpg",
  "vod_year": "1959",
  "vod_remarks": "公有领域长片",
  "type_id": "feature_films",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/house_on_haunted_hill_ipod/house_on_haunted_hill.mp4#备选1$https://archive.org/download/house_on_haunted_hill_ipod/house_on_haunted_hill.ogv#备选2$https://archive.org/download/house_on_haunted_hill_ipod/house_on_haunted_hill_512kb.mp4"
 },
 {
  "vod_id": "ElephantsDream",
  "vod_name": "Elephants Dream",
  "vod_pic": "https://archive.org/download/ElephantsDream/ED-CM-5.1-DVD-C.png",
  "vod_year": "2006",
  "vod_remarks": "经典动画",
  "type_id": "animationandcartoons",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/ElephantsDream/ed_1024.mp4#备选1$https://archive.org/download/ElephantsDream/ed_hd.mp4#备选2$https://archive.org/download/ElephantsDream/ed_hd_512kb.mp4#备选3$https://archive.org/download/ElephantsDream/ed_1024_512kb.mp4#备选4$https://archive.org/download/ElephantsDream/ed_hd.ogv#备选5$https://archive.org/download/ElephantsDream/ed_1024.ogv"
 },
 {
  "vod_id": "Popeye_forPresident",
  "vod_name": "Popeye for President",
  "vod_pic": "https://archive.org/download/Popeye_forPresident/Popeye_forPresident.thumbs/Popeye_forPresident_000001.jpg",
  "vod_year": "1956",
  "vod_remarks": "经典动画",
  "type_id": "animationandcartoons",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/Popeye_forPresident/Popeye_forPresident_512kb.mp4#备选1$https://archive.org/download/Popeye_forPresident/Popeye_forPresident.ogv"
 },
 {
  "vod_id": "popeye_patriotic_popeye",
  "vod_name": "Patriotic Popeye",
  "vod_pic": "https://archive.org/download/popeye_patriotic_popeye/__ia_thumb.jpg",
  "vod_year": "1957",
  "vod_remarks": "经典动画",
  "type_id": "animationandcartoons",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/popeye_patriotic_popeye/popeye_patriotic_popeye_512kb.mp4#备选1$https://archive.org/download/popeye_patriotic_popeye/popeye_patriotic_popeye.ogv"
 },
 {
  "vod_id": "Sintel",
  "vod_name": "Sintel",
  "vod_pic": "https://archive.org/download/Sintel/Poster.jpg",
  "vod_year": "2010",
  "vod_remarks": "经典动画",
  "type_id": "animationandcartoons",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/Sintel/sintel-2048-surround.mp4#备选1$https://archive.org/download/Sintel/sintel-2048-stereo.mp4#备选2$https://archive.org/download/Sintel/sintel-2048-surround_512kb.mp4#备选3$https://archive.org/download/Sintel/sintel-2048-stereo_512kb.mp4#备选4$https://archive.org/download/Sintel/sintel-2048-stereo.ogv"
 },
 {
  "vod_id": "popeye_private_eye_popeye",
  "vod_name": "Private Eye Popeye",
  "vod_pic": "https://archive.org/download/popeye_private_eye_popeye/__ia_thumb.jpg",
  "vod_year": "1954",
  "vod_remarks": "经典动画",
  "type_id": "animationandcartoons",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/popeye_private_eye_popeye/popeye_private_eye_popeye_512kb.mp4#备选1$https://archive.org/download/popeye_private_eye_popeye/popeye_private_eye_popeye.ogv"
 },
 {
  "vod_id": "popeye_shuteye_popeye",
  "vod_name": "Shuteye Popeye",
  "vod_pic": "https://archive.org/download/popeye_shuteye_popeye/__ia_thumb.jpg",
  "vod_year": "1952",
  "vod_remarks": "经典动画",
  "type_id": "animationandcartoons",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/popeye_shuteye_popeye/popeye_shuteye_popeye_512kb.mp4#备选1$https://archive.org/download/popeye_shuteye_popeye/popeye_shuteye_popeye.ogv"
 },
 {
  "vod_id": "spider-mantheanimatedseries",
  "vod_name": "Spider-Man: The Animated Series (Complete 1994 Series) [1080",
  "vod_pic": "https://archive.org/download/spider-mantheanimatedseries/__ia_thumb.jpg",
  "vod_year": "1994",
  "vod_remarks": "经典动画",
  "type_id": "animationandcartoons",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/spider-mantheanimatedseries/01x11%20The%20Hobgoblin%20%28Part%201%29.mkv#备选1$https://archive.org/download/spider-mantheanimatedseries/02x03%20Hydro-Man.mkv#备选2$https://archive.org/download/spider-mantheanimatedseries/02x02%20Battle%20of%20the%20Insidious%20Six.mkv#备选3$https://archive.org/download/spider-mantheanimatedseries/02x01%20The%20Insidious%20Six.mkv#备选4$https://archive.org/download/spider-mantheanimatedseries/01x06%20The%20Sting%20of%20the%20Scorpion.mkv#备选5$https://archive.org/download/spider-mantheanimatedseries/01x05%20The%20Menace%20of%20Mysterio.mkv"
 },
 {
  "vod_id": "popeye_i_dont_scare",
  "vod_name": "Popeye: I Don't Scare",
  "vod_pic": "https://archive.org/download/popeye_i_dont_scare/__ia_thumb.jpg",
  "vod_year": "1956",
  "vod_remarks": "经典动画",
  "type_id": "animationandcartoons",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/popeye_i_dont_scare/popeye_i_dont_scare_512kb.mp4#备选1$https://archive.org/download/popeye_i_dont_scare/popeye_i_dont_scare.ogv"
 },
 {
  "vod_id": "theloneranger_201705",
  "vod_name": "The Lone Ranger TV Show",
  "vod_pic": "https://archive.org/download/theloneranger_201705/__ia_thumb.jpg",
  "vod_year": "1949",
  "vod_remarks": "经典电视剧",
  "type_id": "classic_tv",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/theloneranger_201705/s01e01_EntertheLoneRanger.mp4#备选1$https://archive.org/download/theloneranger_201705/s01e03TheLoneRangersTriumph.mp4#备选2$https://archive.org/download/theloneranger_201705/s01e02_TheLoneRangerFightsOn.mp4#备选3$https://archive.org/download/theloneranger_201705/s01e06_Warhorse.mp4#备选4$https://archive.org/download/theloneranger_201705/s01e01_EntertheLoneRanger.ogv#备选5$https://archive.org/download/theloneranger_201705/s01e07_PeteandPedro.mp4"
 },
 {
  "vod_id": "get-smart",
  "vod_name": "Get Smart",
  "vod_pic": "https://archive.org/download/get-smart/__ia_thumb.jpg",
  "vod_year": "",
  "vod_remarks": "经典电视剧",
  "type_id": "classic_tv",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/get-smart/Get%20Smart%20S01E06%20%28Washington%204%2C%20Indians%203%29.mp4#备选1$https://archive.org/download/get-smart/Get%20Smart%20S01E05%20%28Now%20You%20See%20Him...%20Now%20You%20Don%27t%29.mp4#备选2$https://archive.org/download/get-smart/Get%20Smart%20S01E07%20%28KAOS%20in%20CONTROL%29.mp4#备选3$https://archive.org/download/get-smart/Get%20Smart%20S01E16%20%28Double%20Agent%29.mp4#备选4$https://archive.org/download/get-smart/Get%20Smart%20S01E03%20%28School%20Days%29.mp4#备选5$https://archive.org/download/get-smart/Get%20Smart%20S01E14%20%28Weekend%20Vampire%29.mp4"
 },
 {
  "vod_id": "GreenAcresCompleteSeries",
  "vod_name": "Green Acres Complete Series",
  "vod_pic": "https://archive.org/download/GreenAcresCompleteSeries/GreenAcresCompleteSeries.thumbs/Green%20Acres%20Season%201/Green%20Acres%20-%20001%20-%20Oliver%20Buys%20A%20Farm_000001.jpg",
  "vod_year": "",
  "vod_remarks": "经典电视剧",
  "type_id": "classic_tv",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/GreenAcresCompleteSeries/Green%20Acres%20Season%201/Green%20Acres%20-%20003%20-%20The%20Decorator.mp4#备选1$https://archive.org/download/GreenAcresCompleteSeries/Green%20Acres%20Season%201/Green%20Acres%20-%20002%20-%20Lisa%27s%20First%20Day%20on%20the%20Farm.mp4#备选2$https://archive.org/download/GreenAcresCompleteSeries/Green%20Acres%20Season%201/Green%20Acres%20-%20005%20-%20My%20Husband%2C%20The%20Rooster%20Renter.mp4#备选3$https://archive.org/download/GreenAcresCompleteSeries/Green%20Acres%20Season%201/Green%20Acres%20-%20032%20-%20Uncle%20Ollie.mp4#备选4$https://archive.org/download/GreenAcresCompleteSeries/Green%20Acres%20Season%201/Green%20Acres%20-%20009%20-%20You%20Can%27t%20Plug%20In%20A%202%20with%20a%206.mp4#备选5$https://archive.org/download/GreenAcresCompleteSeries/Green%20Acres%20Season%201/Green%20Acres%20-%20006%20-%20Furniture%2C%20Furniture%2C%20Who%27s%20Got%20the%20Furniture.mp4"
 },
 {
  "vod_id": "ken.-burns.-the.-civil.-war.",
  "vod_name": "Ken. Burns. The. Civil. War.",
  "vod_pic": "https://archive.org/download/ken.-burns.-the.-civil.-war./__ia_thumb.jpg",
  "vod_year": "",
  "vod_remarks": "经典电视剧",
  "type_id": "classic_tv",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/ken.-burns.-the.-civil.-war./Ken.Burns.The.Civil.War.1of9.The.Cause.mp4#备选1$https://archive.org/download/ken.-burns.-the.-civil.-war./Ken.Burns.The.Civil.War.5of9.The.Universe.Of.Battle.mp4#备选2$https://archive.org/download/ken.-burns.-the.-civil.-war./Ken.Burns.The.Civil.War.3of9.Forever.Free.mp4#备选3$https://archive.org/download/ken.-burns.-the.-civil.-war./Ken.Burns.The.Civil.War.7of9.Most.Hallowed.Ground.mp4#备选4$https://archive.org/download/ken.-burns.-the.-civil.-war./Ken.Burns.The.Civil.War.6of9.Valley.Of.The.Shadow.Of.Death.mp4#备选5$https://archive.org/download/ken.-burns.-the.-civil.-war./Ken.Burns.The.Civil.War.8of9.War.Is.All.Hell.mp4"
 },
 {
  "vod_id": "Shogun_Miniseries",
  "vod_name": "Shōgun (miniseries)",
  "vod_pic": "https://archive.org/download/Shogun_Miniseries/Shogun_Miniseries.thumbs/Shogun%201_000001.jpg",
  "vod_year": "1980",
  "vod_remarks": "经典电视剧",
  "type_id": "classic_tv",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/Shogun_Miniseries/Shogun%201.mp4#备选1$https://archive.org/download/Shogun_Miniseries/Shogun%204.mp4#备选2$https://archive.org/download/Shogun_Miniseries/Shogun%203.mp4#备选3$https://archive.org/download/Shogun_Miniseries/Shogun%202.mp4#备选4$https://archive.org/download/Shogun_Miniseries/Shogun%201.ogv#备选5$https://archive.org/download/Shogun_Miniseries/Shogun%204.ogv"
 },
 {
  "vod_id": "Bonanza_-_The_Trail_Gang",
  "vod_name": "Bonanza - The Trail Gang",
  "vod_pic": "https://archive.org/download/Bonanza_-_The_Trail_Gang/Bonanza_-_The_Trail_Gang.thumbs/Bonanza_-_The_Trail_Gang_000001.jpg",
  "vod_year": "",
  "vod_remarks": "经典电视剧",
  "type_id": "classic_tv",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/Bonanza_-_The_Trail_Gang/Bonanza_-_The_Trail_Gang.mp4#备选1$https://archive.org/download/Bonanza_-_The_Trail_Gang/Bonanza_-_The_Trail_Gang.ogv#备选2$https://archive.org/download/Bonanza_-_The_Trail_Gang/Bonanza_-_The_Trail_Gang_512kb.mp4"
 },
 {
  "vod_id": "Bonanza_pd",
  "vod_name": "Bonanza public domain episodes",
  "vod_pic": "https://archive.org/download/Bonanza_pd/Bonanza_pd.thumbs/Bonanza%20s01e19_000001.jpg",
  "vod_year": "",
  "vod_remarks": "经典电视剧",
  "type_id": "classic_tv",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/Bonanza_pd/BonanzaS02e11.mp4#备选1$https://archive.org/download/Bonanza_pd/BonanzaS02e02.mp4#备选2$https://archive.org/download/Bonanza_pd/BonanzaS02e13.mp4#备选3$https://archive.org/download/Bonanza_pd/BonanzaS02e04.mp4#备选4$https://archive.org/download/Bonanza_pd/BonanzaS02e16.ogv#备选5$https://archive.org/download/Bonanza_pd/BonanzaS02e17.ogv"
 },
 {
  "vod_id": "the-world-at-war-1973-thames-television-world-war-two",
  "vod_name": "The World at War (1973) - Thames Television",
  "vod_pic": "https://archive.org/download/the-world-at-war-1973-thames-television-world-war-two/__ia_thumb.jpg",
  "vod_year": "1973",
  "vod_remarks": "经典电视剧",
  "type_id": "classic_tv",
  "vod_play_from": "直链",
  "vod_play_url": "正片$https://archive.org/download/the-world-at-war-1973-thames-television-world-war-two/36%20Making%20the%20Series%20-%20A%2030th%20Anniversary%20Retrospective.mp4#备选1$https://archive.org/download/the-world-at-war-1973-thames-television-world-war-two/34%20The%20Final%20Solution%20Part%20One.mp4#备选2$https://archive.org/download/the-world-at-war-1973-thames-television-world-war-two/35%20The%20Final%20Solution%20Part%20Two.mp4#备选3$https://archive.org/download/the-world-at-war-1973-thames-television-world-war-two/29%20Hitler%27s%20Germany%20-%20Total%20War%20%281939%20-1945%29.mp4#备选4$https://archive.org/download/the-world-at-war-1973-thames-television-world-war-two/28%20Hitler%27s%20Germany%20-%20The%20People%27s%20Community%20%281933%20-%201939%29.mp4#备选5$https://archive.org/download/the-world-at-war-1973-thames-television-world-war-two/37%20Experiences%20of%20War.mp4"
 }
]

CLASSES = [
    {'type_id': 'opensource_movies', 'type_name': '开放电影'},
    {'type_id': 'feature_films', 'type_name': '公有领域长片'},
    {'type_id': 'animationandcartoons', 'type_name': '经典动画'},
    {'type_id': 'classic_tv', 'type_name': '经典电视剧'},
]
PAGE = 24


def _brief(v):
    return {
        'vod_id': v['vod_id'],
        'vod_name': v['vod_name'],
        'vod_pic': v['vod_pic'],
        'vod_year': v['vod_year'],
        'vod_remarks': v['vod_remarks'],
    }


class Spider(BaseSpider):

    def getName(self):
        return 'ArchiveOrg'

    def init(self, extend=''):
        pass

    def homeContent(self, filter):
        return {'class': CLASSES, 'filters': {}}

    def homeVideoContent(self):
        return {'list': [_brief(v) for v in CATALOG[:PAGE]]}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if str(pg).isdigit() else 1
        all_items = [v for v in CATALOG if v['type_id'] == tid]
        items = all_items[(page - 1) * PAGE: page * PAGE]
        return {
            'page': page,
            'pagecount': max(1, -(-len(all_items) // PAGE)),
            'limit': PAGE,
            'total': len(all_items),
            'list': [_brief(v) for v in items],
        }

    def detailContent(self, ids):
        for v in CATALOG:
            if v['vod_id'] == ids[0]:
                return {'list': [v]}
        return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        return {'parse': 0, 'playUrl': '', 'url': id, 'header': {}}

    def searchContent(self, key, quick, pg='1'):
        k = (key or '').lower()
        return {'list': [_brief(v) for v in CATALOG if k in v['vod_name'].lower()]}
