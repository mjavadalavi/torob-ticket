<?php

use App\Http\Controllers\API\BuyController;
use App\Http\Controllers\API\ReserveController;
use App\Http\Controllers\API\SearchController;
use App\Http\Controllers\API\WeeklyScheduleController;
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| API Routes
|--------------------------------------------------------------------------
|
| Here is where you can register API routes for your application. These
| routes are loaded by the RouteServiceProvider and all of them will
| be assigned to the "api" middleware group. Make something great!
|
*/

Route::prefix('ticket')->group(function () {
    Route::match(['get', 'post'], '/list/index', [WeeklyScheduleController::class, "index"])->name('index');
    Route::post('weekly-schedule', [WeeklyScheduleController::class, "store"])->name('store');

    Route::match(['get', 'post'],'/searches', [SearchController::class,"index"])->name('searches');

    Route::post('/reserve', [ReserveController::class, 'store'])->name("reserve_store");
    Route::post('/cancellation', [ReserveController::class, 'cancellation'])->name("reserve_cancellation");

    Route::post('/buy', [BuyController::class, 'store'])->name("buy_store");
    Route::post('/extradition', [BuyController::class, 'extradition'])->name("extradition");

    Route::post('/check', [BuyController::class, 'check'])->name("check");
});
