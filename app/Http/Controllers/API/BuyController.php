<?php

namespace App\Http\Controllers\API;

use App\Enums\BuyStatus;
use App\Enums\Status;
use App\Enums\StatusCode;
use App\Http\Controllers\Controller;
use App\Http\Requests\CheckBuyRequest;
use App\Http\Requests\ExtraditionBuyRequest;
use App\Http\Requests\StoreBuyRequest;
use App\Models\Buy;
use App\Models\Passenger;
use Illuminate\Http\JsonResponse;
use Symfony\Component\HttpFoundation\Response;

class BuyController extends Controller
{
    /**
     * @OA\Post(
     *      path="/StoreBuy",
     *      operationId="StoreBuyRequest",
     *      tags={"Buy"},
     *      summary="Store new Reserve",
     *      description="Returns json of result storing data",
     *      @OA\RequestBody(
     *          required=true,
     *          @OA\JsonContent(ref="App\Http\Requests\StoreReserveRequest")
     *      ),
     *      @OA\Parameter(
     *           description="a hash id of searched by user",
     *           in="path",
     *           name="search_hash",
     *           required=true,
     *           @OA\Schema(type="string"),
     *       ),
     *      @OA\Parameter(
     *           description="count of passengers",
     *           in="path",
     *           name="passenger_count",
     *           required=true,
     *           @OA\Schema(type="integer"),
     *
     *       ),
     *      @OA\Parameter(
     *           description="an aaray of chairs user needed .",
     *           in="path",
     *           name="chairs",
     *           required=true,
     *           @OA\Schema(type="string"),
     *           @OA\Items(
     *               type="array",
     *               @OA\Items()
     *           ),
     *       ),
     *      @OA\Response(
     *          response=201,
     *          description="Successful operation",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          [
     *                              "ticket_id":1,
     *                              "passenger":
     *                               [
     *                                  "firstname":"mohammad",
     *                                  "lastname":"alaaasd",
     *                                  "national_code":"1180769036",
     *                                  "mobile":"09012356486",
     *                               ],
     *                              "message":"your ticket successfully bought"
     *                          ]
     *                     }
     *                 )
     *             )
     *         }
     *       ),
     *      @OA\Response(
     *          response=400,
     *          description="Bad Request",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "status":"HTTP Bad Request",
     *                          "code":"400",
     *                          "data":null
     *                     }
     *                 )
     *             )
     *         }
     *      )
     * )
     */
    public function store(StoreBuyRequest $request): JsonResponse
    {
        if ($request->validated()){
            $passengers = $request->input("passengers");
            $reserve = $request->input("reserve_id");
            $response = [];
            foreach ($passengers as $passenger){
                $db_passenger = Passenger::where("national_code", "like","%".$passenger['national_code']."%")->get();
                if (count($db_passenger)<1){
                    $db_passenger = new Passenger();
                    $db_passenger->firstname = $passenger['firstname'];
                    $db_passenger->lastname = $passenger['lastname'];
                    $db_passenger->national_code = $passenger['national_code'];
                    $db_passenger->mobile = $passenger['mobile'];
                    $db_passenger->save();
                }
                $buy = new Buy();
                $buy->reserve_id = $reserve;
                $buy->passenger_id = $db_passenger->id;
                $buy->status = BuyStatus::Success;
                $buy->save();
                $response[] = ["ticket_id"=>$buy->id, "passenger"=> $passenger, "message" => "your ticket successfully bought"];
            }
            return  response()->json($response)
                ->setStatusCode(Response::HTTP_OK)
                ->header('Content-Type', 'application/json');
        }else{
            return response() ->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Success, "data"=> null])
                ->setStatusCode(Response::HTTP_BAD_REQUEST)
                ->header('Content-Type', 'application/json');
        }
    }


    /**
     * @OA\Post(
     *      path="/ExtraditionBuy",
     *      operationId="ExtraditionBuyRequest",
     *      tags={"Buy"},
     *      summary="extradited a bougth",
     *      description="Returns json of result storing data",
     *      @OA\Parameter(
     *           description="a id of ticket bougth by user",
     *           in="path",
     *           name="ticket_id",
     *           required=true,
     *           @OA\Schema(type="integer"),
     *       ),
     *      @OA\Response(
     *          response=200,
     *          description="Successful operation",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "status":"Success",
     *                          "code":"1",
     *                          "data":"your bougth successfully extradited"
     *                     }
     *                 )
     *             )
     *         }
     *       ),
     *      @OA\Response(
     *          response=404,
     *          description="Not Found",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "status":"Failed",
     *                          "code":"-1",
     *                          "data":null
     *                     }
     *                 )
     *             )
     *         }
     *      ),
     *      @OA\Response(
     *          response=400,
     *          description="Bad Request",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "status":"HTTP Bad Request",
     *                          "code":"400",
     *                          "data":null
     *                     }
     *                 )
     *             )
     *         }
     *      )
     * )
     */
    public function extradition(ExtraditionBuyRequest $request)
    {
        if ($request->validated()){
            $bought = new Buy();

        }else{
            return response() ->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Success, "data"=> null])
                ->setStatusCode(Response::HTTP_BAD_REQUEST)
                ->header('Content-Type', 'application/json');
        }
    }


}
